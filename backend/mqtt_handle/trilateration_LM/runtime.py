"""Realtime MQTT runtime for trilateration Levenberg-Marquardt training."""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional

from backend import crud
from backend.algorithms.trilateration_LM.positioning import TrilaterationPositioning
from backend.algorithms.trilateration_LM.user_state import UserStateTracker
from backend.mqtt_client import mqtt_client


@dataclass
class TagState:
    tag_hex_id: str
    position_x: float = 0.0
    position_y: float = 0.0
    rms_error: float = 0.0
    ranges_cm: Dict[str, float] = field(default_factory=dict)
    filtered_ranges_cm: Dict[str, float] = field(default_factory=dict)


@dataclass
class TrilaterationRun:
    training_run_id: str
    map_id: int
    map_offset_angles: float
    device_hex_ids: List[str]
    device_meta_by_hex: Dict[str, Dict[str, Any]]
    beacons: List[Dict[str, Any]]
    is_active: bool = True
    lock: Lock = field(default_factory=Lock)
    tags: Dict[str, TagState] = field(default_factory=dict)
    positioning_by_tag: Dict[str, TrilaterationPositioning] = field(default_factory=dict)
    user_state_tracker: UserStateTracker = field(default_factory=UserStateTracker)
    topic_callbacks: Dict[str, Any] = field(default_factory=dict)


class TrilaterationRuntime:
    def __init__(self) -> None:
        self.runs: Dict[str, TrilaterationRun] = {}

    def _normalize_hex(self, value: str) -> str:
        value = value.strip().lower()
        if not value.startswith("0x"):
            value = f"0x{value}"
        return value

    def _topic_hex_variants(self, value: str) -> List[str]:
        """Return common topic-id variants to avoid case/padding mismatches.

        MQTT topics are case-sensitive. In the field, hex IDs may appear as
        0xF0 / 0xf0 / 0x0f0 / 0x01 / 0x1, so we subscribe to safe variants.
        Thêm biến thể KHÔNG có tiền tố 0x (01, 1, F0, f0, ...) vì device thực tế gửi như thế.
        """
        raw = value.strip()
        norm = self._normalize_hex(raw)
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

    def start(self, training_run_id: str, map_id: int, selected_device_ids: List[int]) -> Dict[str, Any]:
        existing_run = self.runs.get(training_run_id)
        if existing_run and existing_run.is_active:
            return self.get_state(training_run_id)

        map_data = crud.get_map_by_id(map_id)
        if not map_data:
            raise ValueError("Map not found")

        device_rows = [crud.get_device_by_id(device_id) for device_id in selected_device_ids]
        device_hex_ids: List[str] = []
        device_meta_by_hex: Dict[str, Dict[str, Any]] = {}
        for row in device_rows:
            if not row or not row.get("device_hex_id"):
                continue
            normalized_hex = self._normalize_hex(row["device_hex_id"])
            device_hex_ids.append(normalized_hex)
            device_meta_by_hex[normalized_hex] = {
                "device_id": row.get("device_id"),
                "device_name": row.get("device_name"),
                "device_hex_id": normalized_hex,
            }

        if not device_hex_ids:
            raise ValueError("No valid selected devices found for trilateration runtime")

        beacons = crud.get_map_beacons(map_id)
        master_beacon = next((b for b in beacons if int(b["beacon_type"]) == 4), None)
        slave_beacons = [b for b in beacons if int(b["beacon_type"]) == 3]

        if not master_beacon or (len(slave_beacons) + 1) < 3:
            raise ValueError("Trilateration requires at least 3 UWB beacons including 1 UWB master")

        run = TrilaterationRun(
            training_run_id=training_run_id,
            map_id=map_id,
            map_offset_angles=float(map_data.get("offset_angles", 0.0)),
            device_hex_ids=device_hex_ids,
            device_meta_by_hex=device_meta_by_hex,
            beacons=beacons,
        )

        for tag_hex in device_hex_ids:
            run.tags[tag_hex] = TagState(tag_hex_id=tag_hex)
            run.positioning_by_tag[tag_hex] = TrilaterationPositioning(
                min_beacons=3,
                use_kalman=True,
                process_noise=0.08,
                measurement_noise=0.35,
                use_distance_kalman=True,
                distance_process_variance=0.02,
                distance_measurement_variance=0.25,
                distance_initial_error_variance=1.0,
                distance_innovation_gate=0.9,
                min_distance_m=0.10,
                max_distance_m=15.0,
            )

        master_hex_variants = self._topic_hex_variants(str(master_beacon["beacon_hex_id"]))
        slave_hexes = [self._normalize_hex(beacon["beacon_hex_id"]) for beacon in slave_beacons]

        for slave_hex in slave_hexes:
            def make_range_callback(topic_slave_hex: str):
                def _callback(payload: str) -> None:
                    self._handle_range_payload(training_run_id, topic_slave_hex, payload)
                return _callback

            callback = make_range_callback(slave_hex)
            slave_hex_variants = self._topic_hex_variants(slave_hex)
            for master_hex in master_hex_variants:
                for slave_topic_hex in slave_hex_variants:
                    topic = f"2/uwb_ranging/{master_hex}/{slave_topic_hex}"
                    run.topic_callbacks[topic] = callback
                    mqtt_client.subscribe(topic, callback)

        for tag_hex in device_hex_ids:
            def make_user_callback(topic_tag_hex: str):
                def _callback(payload: str) -> None:
                    self._handle_user_data_payload(training_run_id, topic_tag_hex, payload)
                return _callback

            callback = make_user_callback(tag_hex)
            for tag_topic_hex in self._topic_hex_variants(tag_hex):
                topic = f"uwb_id/{tag_topic_hex}"
                run.topic_callbacks[topic] = callback
                mqtt_client.subscribe(topic, callback)

        self.runs[training_run_id] = run
        return self.get_state(training_run_id)

    def stop(self, training_run_id: str) -> None:
        run = self.runs.get(training_run_id)
        if not run:
            return

        run.is_active = False
        for topic, callback in run.topic_callbacks.items():
            mqtt_client.unsubscribe(topic, callback)
        run.topic_callbacks.clear()

    def remove(self, training_run_id: str) -> None:
        self.stop(training_run_id)
        if training_run_id in self.runs:
            del self.runs[training_run_id]

    def _handle_range_payload(self, training_run_id: str, slave_hex: str, payload: str) -> None:
        run = self.runs.get(training_run_id)
        if not run or not run.is_active:
            return

        with run.lock:
            beacon_positions = {
                self._normalize_hex(b["beacon_hex_id"]): (float(b["coord_x"]), float(b["coord_y"]))
                for b in run.beacons
                if int(b["beacon_type"]) in (3, 4)
            }

            parts = [item.strip() for item in payload.split(",") if item.strip()]
            if len(parts) < 2:
                return

            updated_tags: List[str] = []
            for index in range(0, len(parts) - 1, 2):
                tag_hex = self._normalize_hex(parts[index])
                if tag_hex not in run.tags:
                    continue

                try:
                    distance_cm = float(parts[index + 1])
                except ValueError:
                    continue

                tag_state = run.tags[tag_hex]
                tag_state.ranges_cm[slave_hex] = distance_cm
                updated_tags.append(tag_hex)

            for tag_hex in updated_tags:
                tag_state = run.tags[tag_hex]
                positioning = run.positioning_by_tag.get(tag_hex)
                if not positioning:
                    continue

                solved = positioning.compute_position(beacon_positions, tag_state.ranges_cm)
                if solved:
                    tag_state.position_x = solved["x"]
                    tag_state.position_y = solved["y"]
                    tag_state.rms_error = solved["error"]
                    tag_state.filtered_ranges_cm = solved.get("filtered_distances_cm", {})

    def _handle_user_data_payload(self, training_run_id: str, tag_hex: str, payload: str) -> None:
        run = self.runs.get(training_run_id)
        if not run or not run.is_active:
            return

        with run.lock:
            if tag_hex not in run.tags:
                return
            run.user_state_tracker.update(tag_hex, payload)

    def get_state(self, training_run_id: str) -> Dict[str, Any]:
        run = self.runs.get(training_run_id)
        if not run:
            raise ValueError("Trilateration run not found")

        with run.lock:
            default_telemetry = {
                "tag_hex_id": None,
                "acc_x": None,
                "acc_y": None,
                "acc_z": None,
                "mag_x": None,
                "mag_y": None,
                "mag_z": None,
                "gyro_x": None,
                "gyro_y": None,
                "gyro_z": None,
                "yaw": None,
                "roll": None,
                "pitch": None,
                "valve_open": None,
                "button_a": None,
                "button_b": None,
                "button_c": None,
                "acc_magnitude": None,
                "gyro_magnitude": None,
                "raw_payload": None,
                "last_update_unix": None,
                "filtered_ranges_cm": {},
            }

            return {
                "training_run_id": run.training_run_id,
                "map_id": run.map_id,
                "map_offset_angles": run.map_offset_angles,
                "is_active": run.is_active,
                "tags": [
                    self._merge_tag_state(run, tag, default_telemetry)
                    for tag in run.tags.values()
                ],
                "beacons": run.beacons,
            }

    def _merge_tag_state(self, run: TrilaterationRun, tag: TagState, default_telemetry: Dict[str, Any]) -> Dict[str, Any]:
        telemetry = run.user_state_tracker.get(tag.tag_hex_id)
        device_meta = run.device_meta_by_hex.get(tag.tag_hex_id, {})
        telemetry_data = telemetry.to_dict() if telemetry else dict(default_telemetry)
        telemetry_data["tag_hex_id"] = tag.tag_hex_id
        telemetry_data["device_id"] = device_meta.get("device_id")
        telemetry_data["device_name"] = device_meta.get("device_name")
        telemetry_data["position_x"] = round(tag.position_x, 3)
        telemetry_data["position_y"] = round(tag.position_y, 3)
        telemetry_data["rms_error"] = round(tag.rms_error, 4)
        telemetry_data["yaw_raw"] = telemetry.yaw if telemetry else None
        telemetry_data["yaw_map"] = (
            (telemetry.yaw - run.map_offset_angles) % 360.0
            if telemetry and telemetry.yaw is not None
            else None
        )
        telemetry_data["ranges_cm"] = tag.ranges_cm
        telemetry_data["filtered_ranges_cm"] = tag.filtered_ranges_cm
        return telemetry_data


trilateration_runtime = TrilaterationRuntime()
