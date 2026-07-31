"""MQTT collection runtime for fingerprint data."""
import json
from threading import Lock
from typing import Any, Dict, Optional

from fastapi import HTTPException

from backend import crud, models
from backend.mqtt_client import mqtt_client


def _parse_payload(raw_data: str) -> Dict:
    """Parse JSON payload from fingerprint collection topic.

    Expected format (topic: training_id/<tag_id>):
    {
      "rssi_wifi": {"1": float, "2": float, "3": float, "4": float},
      "rssi_ble":  {"1": float, "2": float, "3": float, "4": float},
      "bno": {
        "acc":   {"x": float, "y": float, "z": float},
        "gyro":  {"x": float, "y": float, "z": float},
        "mag":   {"x": float, "y": float, "z": float},
        "euler": {"yaw": float, "roll": float, "pitch": float}
      }
    }
    """
    def safe_int(val) -> Optional[int]:
        if val is None:
            return None
        try:
            return round(float(val))
        except (TypeError, ValueError):
            return None

    def safe_float(val) -> Optional[float]:
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    data = json.loads(raw_data)

    rssi_wifi = data.get("rssi_wifi") or {}
    rssi_ble = data.get("rssi_ble") or {}
    bno = data.get("bno") or {}
    acc = bno.get("acc") or {}
    gyro = bno.get("gyro") or {}
    mag = bno.get("mag") or {}
    euler = bno.get("euler") or {}

    return {
        'wifi_rssi_1': safe_int(rssi_wifi.get("1")),
        'wifi_rssi_2': safe_int(rssi_wifi.get("2")),
        'wifi_rssi_3': safe_int(rssi_wifi.get("3")),
        'wifi_rssi_4': safe_int(rssi_wifi.get("4")),
        'ble_rssi_1': safe_int(rssi_ble.get("1")),
        'ble_rssi_2': safe_int(rssi_ble.get("2")),
        'ble_rssi_3': safe_int(rssi_ble.get("3")),
        'ble_rssi_4': safe_int(rssi_ble.get("4")),
        'acc_x': safe_float(acc.get("x")),
        'acc_y': safe_float(acc.get("y")),
        'acc_z': safe_float(acc.get("z")),
        'gyro_x': safe_float(gyro.get("x")),
        'gyro_y': safe_float(gyro.get("y")),
        'gyro_z': safe_float(gyro.get("z")),
        'mag_x': safe_float(mag.get("x")),
        'mag_y': safe_float(mag.get("y")),
        'mag_z': safe_float(mag.get("z")),
        'yaw': safe_float(euler.get("yaw")),
        'roll': safe_float(euler.get("roll")),
        'pitch': safe_float(euler.get("pitch")),
    }


class FingerprintCollector:
    """Manage active MQTT collection sessions for map campaigns."""

    def __init__(self) -> None:
        self.active_collections: Dict[str, Dict[str, Any]] = {}

    def start(self, campaign_id: int, cell_id: int, mqtt_topic: str) -> str:
        if not all([campaign_id, cell_id, mqtt_topic]):
            raise HTTPException(status_code=400, detail="Missing required parameters")

        campaign = crud.get_campaign_by_id(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        target_samples = int(campaign["sample_number"])
        if target_samples <= 0:
            raise HTTPException(status_code=400, detail="Campaign target sample number must be greater than 0")

        existing_count = crud.get_cell_sample_count(campaign_id, cell_id)
        if existing_count >= target_samples:
            raise HTTPException(status_code=409, detail="This cell already reached the target sample count")

        if existing_count > 0:
            raise HTTPException(status_code=409, detail="This cell already has collected samples. Reset data before collecting again")

        session_key = f"{campaign_id}_{cell_id}"
        session_state = {
            "campaign_id": campaign_id,
            "cell_id": cell_id,
            "mqtt_topic": mqtt_topic,
            "sample_count": existing_count,
            "target_samples": target_samples,
            "is_active": True,
            "lock": Lock(),
        }

        def mqtt_callback(payload: str) -> None:
            state = self.active_collections.get(session_key)
            if not state or not state.get("is_active"):
                return

            with state["lock"]:
                if state["sample_count"] >= state["target_samples"]:
                    state["is_active"] = False
                    mqtt_client.unsubscribe(mqtt_topic, mqtt_callback)
                    return

                try:
                    sensor_data = _parse_payload(payload)
                    fingerprint = models.FingerprintCreate(
                        campaign_id=campaign_id,
                        cell_id=cell_id,
                        **sensor_data,
                    )
                    crud.create_fingerprint(fingerprint)
                    state["sample_count"] += 1

                    if state["sample_count"] >= state["target_samples"]:
                        state["is_active"] = False
                        mqtt_client.unsubscribe(mqtt_topic, mqtt_callback)
                except Exception as parse_error:  # pragma: no cover
                    print(f"MQTT parsing error: {parse_error}")

        session_state["callback"] = mqtt_callback
        self.active_collections[session_key] = session_state
        mqtt_client.subscribe(mqtt_topic, mqtt_callback)
        return session_key

    def stop(self, session_key: str) -> int:
        state = self.active_collections.get(session_key)
        if not state:
            raise HTTPException(status_code=404, detail="Collection session not found")

        state["is_active"] = False
        mqtt_client.unsubscribe(state["mqtt_topic"], state.get("callback"))
        final_count = int(state["sample_count"])
        del self.active_collections[session_key]
        return final_count

    def get_status(self, session_key: str) -> Dict[str, Any]:
        state = self.active_collections.get(session_key)
        if not state:
            raise HTTPException(status_code=404, detail="Collection session not found")

        return {
            "campaign_id": state["campaign_id"],
            "cell_id": state["cell_id"],
            "mqtt_topic": state["mqtt_topic"],
            "sample_count": state["sample_count"],
            "target_samples": state.get("target_samples", 0),
            "is_active": state["is_active"],
        }


fingerprint_collector = FingerprintCollector()
