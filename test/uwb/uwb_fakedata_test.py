"""Fake MQTT data generator for trilateration LM integration tests.

Publishes two topic families:
1) UWB ranging:
   2/uwb_ranging/<master_hex>/<slave_hex>
   payload: <tag_hex_1>,<dist_cm_1>,<tag_hex_2>,<dist_cm_2>

2) User telemetry:
   2/user_data/<tag_hex>
   payload: acc(3),mag(3),gyro(3),euler(3),valve

Map setup requested by user:
- Ox = 8, Oy = 11
- Beacon coordinates:
	- 0x01 -> (2.50, 10.50)
	- 0x02 -> (5.50, 10.50)
	- 0x03 -> (5.50, 0.50)
	- 0x04 -> (2.50, 0.50)
- Slave beacons: 0x01..0x04
- Master beacon: 0xF0
- Tags: 0xC0 and 0xD0
"""

from __future__ import annotations

import argparse
import math
import random
import signal
import time
from typing import Dict, Tuple

import paho.mqtt.client as mqtt


MASTER_BEACON_HEX = "0xf0"
TAG_HEX_IDS = ("0xd0", "0xc0")

# Map size (Ox, Oy)
MAP_OX = 8.0
MAP_OY = 11.0

# Beacon placement on map 8x11 (user-provided coordinates)
BEACON_POSITIONS: Dict[str, Tuple[float, float]] = {
	"0x01": (2.5, 10.5),
	"0x02": (5.5, 10.5),
	"0x03": (5.5, 0.5),
	"0x04": (2.5, 0.5),
}


def normalize_hex(value: str) -> str:
	text = value.strip().lower()
	if not text.startswith("0x"):
		text = f"0x{text}"
	return text


def clamp(value: float, lo: float, hi: float) -> float:
	return max(lo, min(hi, value))


def position_tag_c0(t: float) -> Tuple[float, float]:
	"""Smooth ellipse-like motion for tag 0xC0."""
	cx = MAP_OX * 0.5
	cy = MAP_OY * 0.5
	rx = MAP_OX * 0.38
	ry = MAP_OY * 0.40
	x = cx + rx * math.cos(0.22 * t)
	y = cy + ry * math.sin(0.22 * t)
	return clamp(x, 0.1, MAP_OX - 0.1), clamp(y, 0.1, MAP_OY - 0.1)


def position_tag_d0(t: float) -> Tuple[float, float]:
	"""Different phase/speed path for tag 0xD0."""
	x = MAP_OX * (0.5 + 0.42 * math.sin(0.17 * t + 0.8))
	y = MAP_OY * (0.5 + 0.42 * math.sin(0.31 * t + 1.2))
	return clamp(x, 0.1, MAP_OX - 0.1), clamp(y, 0.1, MAP_OY - 0.1)


def distance_cm(a: Tuple[float, float], b: Tuple[float, float], noise_sigma_cm: float) -> int:
	"""Euclidean distance with additive Gaussian noise, returned in centimeters."""
	dist_m = math.dist(a, b)
	noisy_cm = dist_m * 100.0 + random.gauss(0.0, noise_sigma_cm)
	return max(1, int(round(noisy_cm)))


def build_user_payload(t: float, tag_hex: str, pos: Tuple[float, float]) -> str:
	"""Build 13-value payload: 3 acc + 3 mag + 3 gyro + 3 euler + valve."""
	x, y = pos

	# Synthetic but stable signals
	acc_x = 0.08 * math.sin(0.9 * t + (0.2 if tag_hex == "0xC0" else 0.6))
	acc_y = 0.07 * math.cos(0.7 * t + (0.1 if tag_hex == "0xC0" else 0.5))
	acc_z = 9.81 + 0.05 * math.sin(0.5 * t)

	mag_x = 22.0 + 1.2 * math.sin(0.15 * t)
	mag_y = -6.0 + 1.0 * math.cos(0.12 * t)
	mag_z = 39.0 + 0.6 * math.sin(0.18 * t)

	gyro_x = 0.03 * math.sin(1.1 * t)
	gyro_y = 0.04 * math.cos(0.9 * t)
	gyro_z = 0.25 * math.sin(0.35 * t + (0.4 if tag_hex == "0xC0" else 1.1))

	# Yaw derived from current position vector around center for readable heading
	# yaw = (math.degrees(math.atan2(y - MAP_OY * 0.5, x - MAP_OX * 0.5)) + 360.0) % 360.0
	yaw = 360
	pitch = 1.5 * math.sin(0.3 * t)
	roll = 1.0 * math.cos(0.27 * t)

	# Toggle valve status periodically
	valve_open = 1 if int(t // 7) % 2 == 0 else 0

	values = [
		acc_x,
		acc_y,
		acc_z,
		mag_x,
		mag_y,
		mag_z,
		gyro_x,
		gyro_y,
		gyro_z,
		yaw,
		roll,
		pitch,
		float(valve_open),
	]
	return ",".join(f"{value:.3f}" for value in values[:-1]) + f",{valve_open:d}"


def publish_once(client: mqtt.Client, t: float, noise_sigma_cm: float, verbose: bool = False) -> None:
	positions = {
		"0xc0": position_tag_c0(t),
		"0xd0": position_tag_d0(t),
	}

	# Publish ranging per slave beacon topic (same structure as requested example)
	for slave_hex in ("0x01", "0x02", "0x03", "0x04"):
		beacon_pos = BEACON_POSITIONS[slave_hex]
		d_d0 = distance_cm(beacon_pos, positions["0xd0"], noise_sigma_cm)
		d_c0 = distance_cm(beacon_pos, positions["0xc0"], noise_sigma_cm)
		payload = f"0xd0,{d_d0},0xc0,{d_c0}"
		topic = f"2/uwb_ranging/{MASTER_BEACON_HEX}/{slave_hex}"
		client.publish(topic, payload, qos=0, retain=False)
		if verbose:
			print(f"{topic} msg:{payload}")

	# Publish user telemetry for both selected tags
	for tag_hex in TAG_HEX_IDS:
		payload = build_user_payload(t, tag_hex, positions[tag_hex])
		topic = f"2/user_data/{tag_hex}"
		client.publish(topic, payload, qos=0, retain=False)
		if verbose:
			print(f"{topic} msg:{payload}")


def main() -> None:
	parser = argparse.ArgumentParser(description="Fake MQTT publisher for UWB trilateration testing")
	parser.add_argument("--broker", default="127.0.0.1", help="MQTT broker host")
	parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
	parser.add_argument("--hz", type=float, default=5.0, help="Publish rate (Hz)")
	parser.add_argument("--noise-cm", type=float, default=8.0, help="Distance noise sigma (cm)")
	parser.add_argument("--verbose", action="store_true", help="Print every published topic and payload")
	args = parser.parse_args()

	interval = 1.0 / max(args.hz, 0.2)
	running = True

	def handle_stop(_sig, _frame) -> None:
		nonlocal running
		running = False

	signal.signal(signal.SIGINT, handle_stop)
	signal.signal(signal.SIGTERM, handle_stop)

	client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="uwb-fakedata-test")
	client.connect(args.broker, args.port, keepalive=60)
	client.loop_start()

	print("Publishing fake UWB data...")
	print(f"Broker: {args.broker}:{args.port}, rate: {args.hz:.2f} Hz")
	print("Master: 0xf0 | Slaves: 0x01..0x04 | Tags: 0xd0, 0xc0")
	print("Beacon coords: 0x01@(2.5,10.5), 0x02@(5.5,10.5), 0x03@(5.5,0.5), 0x04@(2.5,0.5)")

	started = time.time()
	try:
		while running:
			now = time.time() - started
			publish_once(client, now, noise_sigma_cm=args.noise_cm, verbose=args.verbose)
			time.sleep(interval)
	finally:
		client.loop_stop()
		client.disconnect()
		print("Stopped fake data publisher.")


if __name__ == "__main__":
	main()
