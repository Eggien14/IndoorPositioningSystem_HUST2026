"""Dập lửa + hao nước (Pha B). THAM SỐ tinh chỉnh ở đầu file.

Cơ chế:
- Một ô lửa bị "quét" nếu TÂM ô nằm trong cung phun của thiết bị (đúng hình học cung
  vẽ ở frontend: phun tỏa 60°/≤1.5m, phun tia 30°/≤3m, bán kính theo `valve.open`).
- Cường độ giảm 1 sau `seconds_per_level(valve.open)` giây quét liên tục; nội suy
  tuyến tính 5s (van=10) → 1s (van=100). Nhiều thiết bị cùng quét KHÔNG nhanh hơn
  (dùng van lớn nhất) — điểm sẽ được scoring chia đều.
- Hao nước: van mở x% → −(x/100)·WATER_DRAIN_PER_SEC_AT_MAX mỗi giây (tính ở simulator).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

# --- Tham số tinh chỉnh ---
VALVE_MIN_EFFECTIVE = 10.0              # van ≤ ngưỡng này KHÔNG dập được lửa
SECONDS_PER_LEVEL_AT_MIN_VALVE = 3.6    # tại van = VALVE_MIN_EFFECTIVE
SECONDS_PER_LEVEL_AT_MAX_VALVE = 0.5    # tại van = 100

# --- Nước trong bình ---
WATER_MAX = 100.0                       # bình đầy (mặc định; sau này có thể đưa vào DB)
WATER_DRAIN_PER_SEC_AT_MAX_VALVE = 5.0  # van=100 → −5/giây (van x% → −x/100·5)

# Hình học cung phun — PHẢI khớp frontend (training_live_algorithm3.js SPRAY).
SPRAY = {
    "spread": {"half_angle_deg": 30.0, "max_radius_m": 1.5},   # phun tỏa: 60° / 1.5m
    "jet":    {"half_angle_deg": 10.0, "max_radius_m": 2.5},   # phun tia: 30° / 3.0m
}


def water_drain(valve_open: float, dt: float) -> float:
    """Lượng nước hao trong `dt` giây khi van mở `valve_open`% (>=0)."""
    vo = max(0.0, min(valve_open or 0.0, 100.0))
    return vo / 100.0 * WATER_DRAIN_PER_SEC_AT_MAX_VALVE * dt


def spray_mode(valve_mode: float) -> str:
    return "spread" if (valve_mode is None or valve_mode <= 50) else "jet"


def spray_radius_m(valve_open: float, mode: str) -> float:
    return max(0.0, min(valve_open, 100.0)) / 100.0 * SPRAY[mode]["max_radius_m"]


def seconds_per_level(valve_open: float) -> float:
    v = max(VALVE_MIN_EFFECTIVE, min(valve_open, 100.0))
    frac = (v - VALVE_MIN_EFFECTIVE) / (100.0 - VALVE_MIN_EFFECTIVE)
    return SECONDS_PER_LEVEL_AT_MIN_VALVE + frac * (
        SECONDS_PER_LEVEL_AT_MAX_VALVE - SECONDS_PER_LEVEL_AT_MIN_VALVE
    )


def cone_covers(dev_x: float, dev_y: float, heading_deg: float,
                valve_open: float, valve_mode: float,
                cell_cx: float, cell_cy: float) -> bool:
    """Tâm ô (cell_cx, cell_cy) có nằm trong cung phun không? (toạ độ map, Oy hướng lên)."""
    mode = spray_mode(valve_mode)
    radius = spray_radius_m(valve_open, mode)
    if radius <= 0:
        return False
    dx = cell_cx - dev_x
    dy = cell_cy - dev_y
    dist = math.hypot(dx, dy)
    if dist > radius:
        return False
    if dist < 1e-6:
        return True
    # Heading 0° = +Oy ; vector hướng = (sin h, cos h).
    h = math.radians(heading_deg or 0.0)
    hx, hy = math.sin(h), math.cos(h)
    cos_ang = max(-1.0, min(1.0, (dx * hx + dy * hy) / dist))
    ang_deg = math.degrees(math.acos(cos_ang))
    return ang_deg <= SPRAY[mode]["half_angle_deg"]


@dataclass
class Sprayer:
    hex_id: str
    x: float
    y: float
    heading: float       # yaw_map (deg)
    valve_open: float
    valve_mode: float


class ExtinguishEngine:
    """Tích luỹ tiến độ dập theo từng ô qua các tick."""

    def __init__(self) -> None:
        self._progress: Dict[Tuple[int, int], float] = {}

    def step(self, t: float, dt: float, fire, sprayers: List[Sprayer]) -> List[dict]:
        """Quét mọi ô lửa; giảm cường độ ô bị phủ. Trả danh sách sự kiện dập lửa.

        event = {x, y, sprayers:[hex...], levels_reduced, reached_zero, is_root,
                 root_id, original_level, spread_count}
        """
        events: List[dict] = []
        active_keys = set()

        for cell in fire.active_cells():
            key = (cell.x, cell.y)
            active_keys.add(key)
            ccx, ccy = cell.x + 0.5, cell.y + 0.5
            covering = [
                s for s in sprayers
                if cone_covers(s.x, s.y, s.heading, s.valve_open, s.valve_mode, ccx, ccy)
            ]
            if not covering:
                continue

            max_valve = max(s.valve_open for s in covering)
            spl = seconds_per_level(max_valve)
            prog = self._progress.get(key, 0.0) + dt / spl

            reduced_total = 0
            reached_zero = False
            is_root = cell.is_root
            root_id = cell.root_id
            original_level = cell.original_level
            spread_count = cell.spread_count
            while prog >= 1.0 and cell.level > 0:
                reduced, _new_level, rz = fire.reduce_level(cell.x, cell.y, t, 1)
                reduced_total += reduced
                prog -= 1.0
                if rz:
                    reached_zero = True
                    break

            self._progress[key] = 0.0 if cell.level <= 0 else prog

            if reduced_total > 0:
                events.append({
                    "x": cell.x, "y": cell.y,
                    "sprayers": [s.hex_id for s in covering],
                    "levels_reduced": reduced_total,
                    "reached_zero": reached_zero,
                    "is_root": is_root,
                    "root_id": root_id,
                    "original_level": original_level,
                    "spread_count": spread_count,
                })

        # Bỏ tiến độ của ô không còn bị quét/đã tắt.
        for key in [k for k in self._progress if k not in active_keys]:
            del self._progress[key]
        return events
