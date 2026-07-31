"""Algorithm 5 — Trilateration: Tightly-coupled EKF.

File CHỦ của thuật toán 5: điều phối luồng định vị cho MỘT tag bằng EKF nạp thẳng
range thô (backend/algorithms/trilateration_ekf):

  raw range (cm) -> cm->m + clamp -> TrilaterationEKF.step (predict CV + update từng
  range với Jacobian + gate Mahalanobis robust) -> (x, y).

Khác thuật toán 2 (loosely-coupled): KHÔNG giải LS rồi mới lọc — EKF dùng đo thô trực
tiếp (không mất thông tin), và cập nhật được cả khi <3 anchor sau khi đã khởi tạo.
THAM SỐ TINH CHỈNH ở ĐẦU FILE này + đầu file backend/algorithms/trilateration_ekf/ekf.py.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.algorithms.trilateration_ekf import TrilaterationEKF

# ----------------------------------------------------------------------------
# THAM SỐ TINH CHỈNH (Algorithm 5)
# ----------------------------------------------------------------------------
RANGE_MIN_M = 0.10              # loại range quá nhỏ
RANGE_MAX_M = 30.0             # loại range quá lớn


def _normalize_hex(value: str) -> str:
    value = str(value).strip().lower()
    if not value.startswith("0x"):
        value = f"0x{value}"
    return value


class Algorithm5:
    """Định vị trilateration tightly-coupled (EKF) cho MỘT tag."""

    def __init__(self, beacon_positions: Dict[str, Tuple[float, float]]) -> None:
        self.beacons: Dict[str, Tuple[float, float]] = {
            _normalize_hex(h): (float(p[0]), float(p[1])) for h, p in beacon_positions.items()
        }
        self.ekf = TrilaterationEKF()

    def process_ranges(
        self, raw_distances_cm: Dict[str, float], dt: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Nạp tập range thô (cm) của 1 nhịp. Trả trạng thái vị trí hoặc None."""
        distances_m: Dict[str, float] = {}
        for hex_id, distance_cm in raw_distances_cm.items():
            h = _normalize_hex(hex_id)
            if h not in self.beacons:
                continue
            try:
                d_m = float(distance_cm) / 100.0
            except (TypeError, ValueError):
                continue
            if d_m < RANGE_MIN_M or d_m > RANGE_MAX_M:
                continue
            distances_m[h] = d_m

        if not distances_m:
            return None

        result = self.ekf.step(self.beacons, distances_m, dt=dt)
        if result is None:
            return None

        x, y = result
        vx, vy = self.ekf.velocity
        return {
            "x": float(x),
            "y": float(y),
            "velocity": (vx, vy),
            "num_beacons": len(distances_m),
            "ranges_accepted": self.ekf.last_accepted,
            "ranges_rejected": self.ekf.last_rejected,
            "filtered_distances_cm": {h: round(d * 100.0, 1) for h, d in distances_m.items()},
        }

    def reset(self) -> None:
        self.ekf.reset()
