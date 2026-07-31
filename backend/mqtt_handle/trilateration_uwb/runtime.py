"""Realtime MQTT runtime cho thuật toán UWB (2 loosely-LM & 5 tightly-EKF).

Tầng TRUYỀN THÔNG — mẫu theo `transformer_pdr_eskf/runtime.py` (algo 3) nhưng nhận UWB:
- NHẬN range: subscribe `2/uwb_ranging/<master_hex>/<slave_hex>` (mọi biến thể hex
  case/padding) cho TỪNG slave — giữ NGUYÊN logic lấy master/slave beacon của runtime
  trilateration cũ (phần backend này đã chạy ổn). Payload `<tag>,<dist_cm>,...`.
- NHẬN telemetry: subscribe `uwb_id/<tag>` (yaw/valve/button/IMU) — chỉ cho FOV +
  mô phỏng lửa, KHÔNG dùng để định vị.
- Mỗi range -> `uwb_manager.feed_range(...)`; có vị trí mới -> publish `user_pos/<tag>`.
- Telemetry -> `uwb_manager.feed_user(...)`.

Brain định vị (Algorithm2/Algorithm5) + mô phỏng lửa + điểm + publish fire_data (Pha B)
nằm ở lớp điều phối (backend/algorithm_uwb.py + main.py), KHÔNG ở tầng transport này.
Phần GỬI (user_pos/fire_data) Y HỆT algo 3.
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional

from backend import crud
from backend.algorithm_uwb import uwb_manager
from backend.mqtt_client import mqtt_client
from backend.mqtt_handle.server_2_device import publish_user_pos


def _normalize_hex(value: str) -> str:
    value = str(value).strip().lower()
    if not value.startswith("0x"):
        value = f"0x{value}"
    return value


def _topic_hex_variants(value: str) -> List[str]:
    """Các biến thể hex của một id để subscribe (giống trilateration/algo3 runtime).

    MQTT topic phân biệt hoa/thường + padding; firmware có thể gửi 0xF0/0xf0/0x0f0/
    0x01/0x1 ... nên subscribe nhiều biến thể an toàn.
    Thêm biến thể KHÔNG có tiền tố 0x (01, 1, F0, f0, ...) vì device thực tế gửi như thế.
    """
    raw = str(value).strip()
    norm = _normalize_hex(raw)
    variants = {raw, norm, norm.upper().replace("0X", "0x")}
    try:
        number = int(norm, 16)
        minimal = f"0x{number:x}"
        padded2 = f"0x{number:02x}"
        variants.add(minimal)
        variants.add(minimal.upper().replace("0X", "0x"))
        variants.add(padded2)
        variants.add(padded2.upper().replace("0X", "0x"))
        
        # Thêm biến thể KHÔNG có tiền tố 0x (vì device publish không có 0x)
        minimal_no_prefix = f"{number:x}"
        padded2_no_prefix = f"{number:02x}"
        variants.add(minimal_no_prefix)
        variants.add(minimal_no_prefix.upper())
        variants.add(padded2_no_prefix)
        variants.add(padded2_no_prefix.upper())
    except ValueError:
        pass
    return sorted(variants)


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _magnitude(d: Dict[str, Any]) -> Optional[float]:
    xs = [_to_float(d.get("x")), _to_float(d.get("y")), _to_float(d.get("z"))]
    if any(v is None for v in xs):
        return None
    return math.sqrt(sum(float(v) ** 2 for v in xs))


def _parse_user_payload(payload: str) -> Optional[Dict[str, Any]]:
    """Parse JSON topic uwb_id/<tag>. Trả sample cho manager.feed_user, None nếu lỗi.

    Định dạng (Source/mqtt_topic.txt):
      {"bno":{"acc":{x,y,z},"gyro":{x,y,z},"mag":{x,y,z},"euler":{yaw,roll,pitch}},
       "valve":{"open":float, "mode":float?}, "button":{"A":bool,"B":bool,"C":bool}}
    `valve.mode` có thể KHÔNG có ở thiết bị UWB thật -> mặc định spread ở manager.
    """
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, ValueError, TypeError):
        return None

    bno = data.get("bno") or {}
    acc = bno.get("acc") or {}
    gyro = bno.get("gyro") or {}
    euler = bno.get("euler") or {}
    valve = data.get("valve") or {}
    button = data.get("button") or {}

    return {
        "yaw": _to_float(euler.get("yaw")),
        "valve_open": _to_float(valve.get("open")),
        "valve_mode": _to_float(valve.get("mode")),
        "button_a": bool(button["A"]) if "A" in button else None,
        "button_b": bool(button["B"]) if "B" in button else None,
        "button_c": bool(button["C"]) if "C" in button else None,
        "acc_magnitude": _magnitude(acc),
        "gyro_magnitude": _magnitude(gyro),
    }


class UWBRuntime:
    """Vòng đời subscribe/parse/feed/publish cho mỗi training_run_id của algo 2 & 5."""

    def __init__(self) -> None:
        # run_id -> {topic: callback} để unsubscribe khi dừng.
        self._topic_callbacks: Dict[str, Dict[str, Any]] = {}

    def start(
        self,
        training_run_id: str,
        algorithm: int,
        map_id: int,
        selected_device_ids: List[int],
        start_x: Optional[float] = None,
        start_y: Optional[float] = None,
        root_fires: Optional[List[Dict[str, Any]]] = None,
        duration_seconds: int = 0,
        assembly_point: Optional[tuple] = None,
        admin_enabled: bool = False,
    ) -> Dict[str, Any]:
        if uwb_manager.has_run(training_run_id):
            return uwb_manager.get_state(training_run_id)

        map_data = crud.get_map_by_id(map_id)
        if not map_data:
            raise ValueError("Map not found")

        device_meta: List[Dict[str, Any]] = []
        for device_id in selected_device_ids:
            row = crud.get_device_by_id(device_id)
            if not row or not row.get("device_hex_id"):
                continue
            device_meta.append({
                "device_id": row.get("device_id"),
                "device_name": row.get("device_name"),
                "device_hex_id": _normalize_hex(row["device_hex_id"]),
                "water_capacity": row.get("water_capacity"),
            })
        if not device_meta:
            raise ValueError("No valid selected devices found for UWB runtime")

        beacons = crud.get_map_beacons(map_id)
        master_beacon = next((b for b in beacons if int(b["beacon_type"]) == 4), None)
        slave_beacons = [b for b in beacons if int(b["beacon_type"]) == 3]
        if not master_beacon or (len(slave_beacons) + 1) < 3:
            raise ValueError("Trilateration requires at least 3 UWB beacons including 1 UWB master")

        beacon_positions = {
            _normalize_hex(b["beacon_hex_id"]): (float(b["coord_x"]), float(b["coord_y"]))
            for b in beacons
            if int(b["beacon_type"]) in (3, 4)
        }

        length_x = int(map_data["length_x"])
        width_y = int(map_data["width_y"])
        if start_x is None:
            start_x = length_x / 2.0
        if start_y is None:
            start_y = width_y / 2.0

        uwb_manager.start_run(
            run_id=training_run_id,
            algorithm=int(algorithm),
            map_id=map_id,
            map_offset_angle=float(map_data.get("offset_angles", 0.0)),
            length_x=length_x,
            width_y=width_y,
            beacon_positions=beacon_positions,
            beacons=beacons,
            device_meta=device_meta,
            start_x=float(start_x),
            start_y=float(start_y),
            root_fires=root_fires or [],
            duration_seconds=int(duration_seconds or 0),
            assembly_point=assembly_point,
            admin_enabled=bool(admin_enabled),
        )

        run_callbacks: Dict[str, Any] = {}

        # NHẬN range: `2/uwb_ranging/<master>/<slave>` (mọi biến thể hex), 1 callback/slave.
        master_hex_variants = _topic_hex_variants(str(master_beacon["beacon_hex_id"]))
        for slave in slave_beacons:
            slave_hex = _normalize_hex(slave["beacon_hex_id"])

            def make_range_cb(bound_run_id: str, bound_slave_hex: str):
                def _callback(payload: str) -> None:
                    self._handle_range(bound_run_id, bound_slave_hex, payload)
                return _callback

            callback = make_range_cb(training_run_id, slave_hex)
            for master_hex in master_hex_variants:
                for slave_topic_hex in _topic_hex_variants(slave_hex):
                    topic = f"2/uwb_ranging/{master_hex}/{slave_topic_hex}"
                    run_callbacks[topic] = callback
                    mqtt_client.subscribe(topic, callback)

        # NHẬN telemetry: `uwb_id/<tag>` (mọi biến thể hex), 1 callback/thiết bị.
        for meta in device_meta:
            tag_hex = meta["device_hex_id"]

            def make_user_cb(bound_run_id: str, bound_tag_hex: str):
                def _callback(payload: str) -> None:
                    sample = _parse_user_payload(payload)
                    if sample is not None:
                        uwb_manager.feed_user(bound_run_id, bound_tag_hex, sample)
                return _callback

            callback = make_user_cb(training_run_id, tag_hex)
            for tag_topic_hex in _topic_hex_variants(tag_hex):
                topic = f"uwb_id/{tag_topic_hex}"
                run_callbacks[topic] = callback
                mqtt_client.subscribe(topic, callback)

        self._topic_callbacks[training_run_id] = run_callbacks
        return uwb_manager.get_state(training_run_id)

    def _handle_range(self, run_id: str, slave_hex: str, payload: str) -> None:
        """Parse `<tag>,<dist_cm>,...` -> feed_range cho từng tag; publish user_pos khi đổi."""
        parts = [item.strip() for item in str(payload).split(",") if item.strip()]
        if len(parts) < 2:
            return
        for index in range(0, len(parts) - 1, 2):
            tag_hex = parts[index]
            try:
                distance_cm = float(parts[index + 1])
            except ValueError:
                continue
            result = uwb_manager.feed_range(run_id, tag_hex, slave_hex, distance_cm)
            if result is not None:
                x, y = result
                score = uwb_manager.get_device_score(run_id, tag_hex)
                publish_user_pos(tag_hex, x, y, score)

    def get_state(self, training_run_id: str) -> Dict[str, Any]:
        return uwb_manager.get_state(training_run_id)

    def stop(self, training_run_id: str) -> None:
        callbacks = self._topic_callbacks.get(training_run_id, {})
        for topic, callback in callbacks.items():
            mqtt_client.unsubscribe(topic, callback)
        self._topic_callbacks.pop(training_run_id, None)
        uwb_manager.stop_run(training_run_id)

    def remove(self, training_run_id: str) -> None:
        self.stop(training_run_id)
        uwb_manager.remove_run(training_run_id)


uwb_runtime = UWBRuntime()
