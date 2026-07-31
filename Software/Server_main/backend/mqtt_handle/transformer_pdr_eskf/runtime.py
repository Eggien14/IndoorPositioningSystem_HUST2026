"""Realtime MQTT runtime for Algorithm 3 (Transformer + PDR + ESKF).

Tầng TRUYỀN THÔNG cho thuật toán 3 — mẫu theo `trilateration_LM/runtime.py`:
- Subscribe `reality_id/<tag_id>` (mục "RSSI gửi chế độ reality (Device -> Server)"
  trong Source/mqtt_topic.txt) cho từng thiết bị đã chọn, kèm các biến thể hex
  (case/padding) như trilateration.
- Mỗi tin nhắn -> `_parse_reality_payload` -> đẩy RSSI+IMU+valve vào
  `algorithm3_manager.feed(...)` (bộ não trong backend/algorithm_3.py).
- Khi có vị trí mới -> publish `user_pos/<tag_id>` về thiết bị
  (backend/mqtt_handle/server_2_device).

Engine lan/dập lửa + tính điểm + publish fire_data (Pha B) sẽ được nối vào ở lớp
điều phối (main.py / Algorithm3Manager), KHÔNG nằm ở tầng transport này.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend import crud
from backend.algorithm_3 import algorithm3_manager
from backend.algorithms.pdr import config as pdr_config
from backend.algorithms.transformer import config as tf_config
from backend.mqtt_client import mqtt_client
from backend.mqtt_handle.server_2_device import publish_user_pos


def _normalize_hex(value: str) -> str:
    value = str(value).strip().lower()
    if not value.startswith("0x"):
        value = f"0x{value}"
    return value


def _topic_hex_variants(value: str) -> List[str]:
    """Các biến thể hex của một id để subscribe (giống trilateration runtime).

    MQTT topic phân biệt hoa/thường + padding; firmware có thể gửi 0xF0/0xf0/
    0x0f0/0x01/0x1 ... nên subscribe nhiều biến thể an toàn.
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


def _parse_reality_payload(payload: str) -> Optional[Dict[str, Any]]:
    """Parse JSON topic reality_id/<tag>. Trả sample dict cho manager.feed, None nếu lỗi.

    RSSI theo thứ tự model: [wifi1..4, ble1..4]. Mẫu RSSI ngoài dải hợp lệ sẽ bị
    Algorithm3.process_rssi tự loại — ở đây chỉ trích xuất, không lọc.
    """
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, ValueError, TypeError):
        return None

    bno = data.get("bno") or {}
    acc = bno.get("acc") or {}
    euler = bno.get("euler") or {}
    rw = data.get("rssi_wifi") or {}
    rb = data.get("rssi_ble") or {}
    valve = data.get("valve") or {}
    button = data.get("button") or {}

    rssi = [
        _to_float(rw.get("1")), _to_float(rw.get("2")),
        _to_float(rw.get("3")), _to_float(rw.get("4")),
        _to_float(rb.get("1")), _to_float(rb.get("2")),
        _to_float(rb.get("3")), _to_float(rb.get("4")),
    ]

    return {
        "rssi": rssi,
        "acc_x": _to_float(acc.get("x")),
        "acc_y": _to_float(acc.get("y")),
        "acc_z": _to_float(acc.get("z")),
        "yaw": _to_float(euler.get("yaw")),
        "valve_open": _to_float(valve.get("open")),
        "valve_mode": _to_float(valve.get("mode")),
        "button_a": bool(button["A"]) if "A" in button else None,
        "button_b": bool(button["B"]) if "B" in button else None,
        "button_c": bool(button["C"]) if "C" in button else None,
    }


def resolve_model_dir(map_id: int, campaign_id: int) -> Path:
    """Đường dẫn model: backend/algorithms/transformer/model/map_{id}/campaign_{id}."""
    return (
        Path(tf_config.CONFIG.TRANSFORMER_DIR)
        / "model"
        / f"map_{map_id}"
        / f"campaign_{campaign_id}"
    )


def model_exists(map_id: int, campaign_id: int) -> bool:
    model_dir = resolve_model_dir(map_id, campaign_id)
    return (model_dir / "transformer_model.pt").exists() and (model_dir / "scaler.joblib").exists()


class Algorithm3Runtime:
    """Vòng đời subscribe/parse/feed/publish cho mỗi training_run_id của algo 3."""

    def __init__(self) -> None:
        # run_id -> {topic: callback} để unsubscribe khi dừng.
        self._topic_callbacks: Dict[str, Dict[str, Any]] = {}

    def start(
        self,
        training_run_id: str,
        map_id: int,
        selected_device_ids: List[int],
        campaign_id: int,
        start_x: Optional[float] = None,
        start_y: Optional[float] = None,
        offset_angle_bno: Optional[float] = None,
        root_fires: Optional[List[Dict[str, Any]]] = None,
        duration_seconds: int = 0,
        assembly_point: Optional[tuple] = None,
        admin_enabled: bool = False,
    ) -> Dict[str, Any]:
        if algorithm3_manager.has_run(training_run_id):
            return algorithm3_manager.get_state(training_run_id)

        map_data = crud.get_map_by_id(map_id)
        if not map_data:
            raise ValueError("Map not found")

        model_dir = resolve_model_dir(map_id, campaign_id)
        if not model_exists(map_id, campaign_id):
            raise ValueError(
                f"Chưa có model cho map {map_id} / campaign {campaign_id} "
                f"(thiếu transformer_model.pt hoặc scaler.joblib trong {model_dir})"
            )

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
            raise ValueError("No valid selected devices found for Algorithm 3 runtime")

        length_x = int(map_data["length_x"])
        width_y = int(map_data["width_y"])
        if start_x is None:
            start_x = length_x / 2.0
        if start_y is None:
            start_y = width_y / 2.0
        if offset_angle_bno is None:
            offset_angle_bno = float(pdr_config.DEFAULT_OFFSET_ANGLE_BNO)

        algorithm3_manager.start_run(
            run_id=training_run_id,
            map_id=map_id,
            map_offset_angle=float(map_data.get("offset_angles", 0.0)),
            length_x=length_x,
            width_y=width_y,
            model_dir=model_dir,
            device_meta=device_meta,
            offset_angle_bno=float(offset_angle_bno),
            start_x=float(start_x),
            start_y=float(start_y),
            root_fires=root_fires or [],
            duration_seconds=int(duration_seconds or 0),
            assembly_point=assembly_point,
            admin_enabled=bool(admin_enabled),
        )

        # Subscribe reality_id/<tag> (các biến thể hex) cho từng thiết bị.
        run_callbacks: Dict[str, Any] = {}
        for meta in device_meta:
            tag_hex = meta["device_hex_id"]

            def make_callback(bound_run_id: str, bound_tag_hex: str):
                def _callback(payload: str) -> None:
                    sample = _parse_reality_payload(payload)
                    if sample is None:
                        return
                    result = algorithm3_manager.feed(bound_run_id, bound_tag_hex, sample)
                    if result is not None:
                        x, y = result
                        score = algorithm3_manager.get_device_score(bound_run_id, bound_tag_hex)
                        publish_user_pos(bound_tag_hex, x, y, score)
                return _callback

            callback = make_callback(training_run_id, tag_hex)
            for topic_hex in _topic_hex_variants(tag_hex):
                topic = f"reality_id/{topic_hex}"
                run_callbacks[topic] = callback
                mqtt_client.subscribe(topic, callback)

        self._topic_callbacks[training_run_id] = run_callbacks
        return algorithm3_manager.get_state(training_run_id)

    def get_state(self, training_run_id: str) -> Dict[str, Any]:
        return algorithm3_manager.get_state(training_run_id)

    def stop(self, training_run_id: str) -> None:
        callbacks = self._topic_callbacks.get(training_run_id, {})
        for topic, callback in callbacks.items():
            mqtt_client.unsubscribe(topic, callback)
        self._topic_callbacks.pop(training_run_id, None)
        algorithm3_manager.stop_run(training_run_id)

    def remove(self, training_run_id: str) -> None:
        self.stop(training_run_id)
        algorithm3_manager.remove_run(training_run_id)


algorithm3_runtime = Algorithm3Runtime()
