"""Replay a fingerprint/reality CSV as MQTT JSON on topic reality_id/<tag>.

Use this to feed the live Algorithm 3 server with the same dataset used by
test/tran_pdr_eskf without a physical device.

Example:
  .\\venv\\Scripts\\python.exe test\\mqtt_fake_test\\mqtt_fake_test.py
  .\\venv\\Scripts\\python.exe test\\mqtt_fake_test\\mqtt_fake_test.py --tag-id 0x14 --hz 17.1
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import paho.mqtt.client as mqtt

TEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_DIR.parents[1]
DEFAULT_DATASET = TEST_DIR / "dataset" / "result" / "test_case_D8_1_1.csv"
DEFAULT_TOPIC = "reality_id/14"
DEFAULT_HZ = 17.1

RSSI_COLUMNS = [
    "wifi_rssi_1", "wifi_rssi_2", "wifi_rssi_3", "wifi_rssi_4",
    "ble_rssi_1", "ble_rssi_2", "ble_rssi_3", "ble_rssi_4",
]
IMU_COLUMNS = [
    "acc_x", "acc_y", "acc_z",
    "gyro_x", "gyro_y", "gyro_z",
    "mag_x", "mag_y", "mag_z",
    "yaw", "roll", "pitch",
]


def _to_json_number(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def row_to_payload(row: pd.Series, valve_open: float = 0.0, valve_mode: float = 100.0) -> str:
    """Build reality_id JSON payload from one CSV row (fingerprint export format)."""
    rssi_wifi: Dict[str, Optional[float]] = {}
    rssi_ble: Dict[str, Optional[float]] = {}
    for i in range(1, 5):
        rssi_wifi[str(i)] = _to_json_number(row.get(f"wifi_rssi_{i}"))
        rssi_ble[str(i)] = _to_json_number(row.get(f"ble_rssi_{i}"))

    payload: Dict[str, Any] = {
        "rssi_wifi": rssi_wifi,
        "rssi_ble": rssi_ble,
        "bno": {
            "acc": {
                "x": _to_json_number(row.get("acc_x")),
                "y": _to_json_number(row.get("acc_y")),
                "z": _to_json_number(row.get("acc_z")),
            },
            "gyro": {
                "x": _to_json_number(row.get("gyro_x")),
                "y": _to_json_number(row.get("gyro_y")),
                "z": _to_json_number(row.get("gyro_z")),
            },
            "mag": {
                "x": _to_json_number(row.get("mag_x")),
                "y": _to_json_number(row.get("mag_y")),
                "z": _to_json_number(row.get("mag_z")),
            },
            "euler": {
                "yaw": _to_json_number(row.get("yaw")),
                "roll": _to_json_number(row.get("roll")),
                "pitch": _to_json_number(row.get("pitch")),
            },
        },
        "valve": {"open": float(valve_open), "mode": float(valve_mode)},
        "button": {"A": 0, "B": 0, "C": 0},
    }
    return json.dumps(payload, separators=(",", ":"))


def resolve_topic(tag_id: str, topic: Optional[str]) -> str:
    if topic:
        return topic.strip()
    tag = str(tag_id).strip()
    if "/" in tag:
        return tag
    return f"reality_id/{tag}"


def load_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    df = pd.read_csv(path)
    missing = [c for c in RSSI_COLUMNS + IMU_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset missing columns: {missing}")
    return df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish CSV rows as reality_id MQTT JSON for Algorithm 3 testing."
    )
    parser.add_argument("--broker", default="127.0.0.1", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument(
        "--topic",
        default=None,
        help=f"Full MQTT topic (default: reality_id/<tag-id>, e.g. {DEFAULT_TOPIC})",
    )
    parser.add_argument(
        "--tag-id",
        default="14",
        help="Tag hex/id appended to reality_id/ when --topic is omitted (default: 14)",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="CSV path (fingerprint export / test_case format)",
    )
    parser.add_argument("--hz", type=float, default=DEFAULT_HZ, help="Publish rate (Hz)")
    parser.add_argument("--loop", action="store_true", help="Restart dataset when finished")
    parser.add_argument("--verbose", action="store_true", help="Print each published row index")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    topic = resolve_topic(args.tag_id, args.topic)
    dataframe = load_dataset(args.dataset.resolve())
    interval = 1.0 / max(args.hz, 0.1)

    running = True

    def handle_stop(_sig, _frame) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="mqtt-fake-reality-test")
    client.connect(args.broker, args.port, keepalive=60)
    client.loop_start()

    print("MQTT fake reality publisher")
    print(f"  Broker : {args.broker}:{args.port}")
    print(f"  Topic  : {topic}")
    print(f"  Dataset: {args.dataset}")
    print(f"  Rows   : {len(dataframe):,} @ {args.hz:.2f} Hz")
    print("  Ctrl+C to stop\n")

    pass_no = 0
    try:
        while running:
            pass_no += 1
            for row_idx, (_, row) in enumerate(dataframe.iterrows(), start=1):
                if not running:
                    break
                payload = row_to_payload(row)
                client.publish(topic, payload, qos=0, retain=False)
                if args.verbose:
                    print(f"pass={pass_no} row={row_idx}/{len(dataframe)}")
                time.sleep(interval)
            if not args.loop:
                break
            if running:
                print(f"Pass {pass_no} finished, looping...")
    finally:
        client.loop_stop()
        client.disconnect()
        print("Stopped.")


if __name__ == "__main__":
    main()
