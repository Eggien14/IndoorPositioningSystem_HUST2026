"""User telemetry parsing for trilateration Levenberg-Marquardt runtime."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from math import sqrt
from time import time
from typing import Any, Dict, Optional


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class UserState:
    tag_hex_id: str
    acc_x: Optional[float] = None
    acc_y: Optional[float] = None
    acc_z: Optional[float] = None
    mag_x: Optional[float] = None
    mag_y: Optional[float] = None
    mag_z: Optional[float] = None
    gyro_x: Optional[float] = None
    gyro_y: Optional[float] = None
    gyro_z: Optional[float] = None
    yaw: Optional[float] = None
    roll: Optional[float] = None
    pitch: Optional[float] = None
    valve_open: Optional[float] = None
    button_a: Optional[bool] = None
    button_b: Optional[bool] = None
    button_c: Optional[bool] = None
    raw_payload: Optional[str] = None
    last_update_unix: Optional[float] = None

    def update_from_payload(self, payload: str) -> bool:
        """Parse JSON payload from topic uwb_id/<tag_id>.

        Expected format (from mqtt_topic.txt):
        {
          "bno": {
            "acc":   {"x": float, "y": float, "z": float},
            "gyro":  {"x": float, "y": float, "z": float},
            "mag":   {"x": float, "y": float, "z": float},
            "euler": {"yaw": float, "roll": float, "pitch": float}
          },
          "valve":  {"open": float, "mode": float},
          "button": {"A": bool, "B": bool, "C": bool}
        }
        """
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            return False

        try:
            bno = data.get("bno") or {}
            acc = bno.get("acc") or {}
            gyro = bno.get("gyro") or {}
            mag = bno.get("mag") or {}
            euler = bno.get("euler") or {}

            self.acc_x = _to_float(acc.get("x"))
            self.acc_y = _to_float(acc.get("y"))
            self.acc_z = _to_float(acc.get("z"))
            self.gyro_x = _to_float(gyro.get("x"))
            self.gyro_y = _to_float(gyro.get("y"))
            self.gyro_z = _to_float(gyro.get("z"))
            self.mag_x = _to_float(mag.get("x"))
            self.mag_y = _to_float(mag.get("y"))
            self.mag_z = _to_float(mag.get("z"))
            self.yaw = _to_float(euler.get("yaw"))
            self.roll = _to_float(euler.get("roll"))
            self.pitch = _to_float(euler.get("pitch"))

            valve = data.get("valve") or {}
            self.valve_open = _to_float(valve.get("open"))

            button = data.get("button") or {}
            self.button_a = bool(button["A"]) if "A" in button else None
            self.button_b = bool(button["B"]) if "B" in button else None
            self.button_c = bool(button["C"]) if "C" in button else None

            self.raw_payload = payload
            self.last_update_unix = time()
            return True
        except Exception:
            return False

    @property
    def acc_magnitude(self) -> Optional[float]:
        values = [self.acc_x, self.acc_y, self.acc_z]
        if any(v is None for v in values):
            return None
        return sqrt(sum(float(v) ** 2 for v in values if v is not None))

    @property
    def gyro_magnitude(self) -> Optional[float]:
        values = [self.gyro_x, self.gyro_y, self.gyro_z]
        if any(v is None for v in values):
            return None
        return sqrt(sum(float(v) ** 2 for v in values if v is not None))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tag_hex_id": self.tag_hex_id,
            "acc_x": self.acc_x,
            "acc_y": self.acc_y,
            "acc_z": self.acc_z,
            "mag_x": self.mag_x,
            "mag_y": self.mag_y,
            "mag_z": self.mag_z,
            "gyro_x": self.gyro_x,
            "gyro_y": self.gyro_y,
            "gyro_z": self.gyro_z,
            "yaw": self.yaw,
            "roll": self.roll,
            "pitch": self.pitch,
            "valve_open": self.valve_open,
            "button_a": self.button_a,
            "button_b": self.button_b,
            "button_c": self.button_c,
            "acc_magnitude": self.acc_magnitude,
            "gyro_magnitude": self.gyro_magnitude,
            "raw_payload": self.raw_payload,
            "last_update_unix": self.last_update_unix,
        }


@dataclass
class UserStateTracker:
    states: Dict[str, UserState] = field(default_factory=dict)

    def update(self, tag_hex_id: str, payload: str) -> Optional[UserState]:
        state = self.states.get(tag_hex_id)
        if state is None:
            state = UserState(tag_hex_id=tag_hex_id)
            self.states[tag_hex_id] = state

        if not state.update_from_payload(payload):
            return None
        return state

    def get(self, tag_hex_id: str) -> Optional[UserState]:
        return self.states.get(tag_hex_id)

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        return {tag_hex_id: state.to_dict() for tag_hex_id, state in self.states.items()}
