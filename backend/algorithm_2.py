"""Algorithm 2 — Trilateration: Robust LM (loosely-coupled).

File CHỦ của thuật toán 2: gọi các hàm xử lý trong backend/algorithms/trilateration_LM
và điều phối luồng định vị cho MỘT tag:

  raw range (cm) -> cm->m + clamp -> Kalman range/anchor (distance_kalman) ->
  LLS seed + LM robust (engine: Huber + WLS + covariance P) ->
  Constant-Velocity Kalman vị trí (position_kf, R thích nghi theo P).

THAM SỐ TINH CHỈNH ở ĐẦU FILE (chi tiết từng khối ở đầu file con tương ứng).
Tầng truyền thông (MQTT runtime) + trang realtime sẽ nối ở bước sau, dùng class này.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.algorithms.trilateration_LM.distance_kalman import DistanceKalmanFilterBank
from backend.algorithms.trilateration_LM.engine import solve_trilateration_robust
from backend.algorithms.trilateration_LM.position_kf import ConstantVelocityKF

# ----------------------------------------------------------------------------
# THAM SỐ TINH CHỈNH (Algorithm 2)
# ----------------------------------------------------------------------------
RANGE_MIN_M = 0.10              # loại range quá nhỏ (lỗi/đo gần 0)
RANGE_MAX_M = 30.0             # loại range quá lớn (ngoài phòng)
MIN_BEACONS = 3                # số anchor tối thiểu để giải
USE_DISTANCE_KALMAN = True     # bật lọc Kalman từng anchor (Bước 0)
USE_WLS_PRIOR = True           # trọng số WLS = 1/variance của distance filter (chuẩn hoá mean≈1)
WARM_START = True              # dùng vị trí lần trước làm điểm khởi tạo LM


def _normalize_hex(value: str) -> str:
    value = str(value).strip().lower()
    if not value.startswith("0x"):
        value = f"0x{value}"
    return value


class Algorithm2:
    """Định vị trilateration loosely-coupled cho MỘT tag."""

    def __init__(self, beacon_positions: Dict[str, Tuple[float, float]]) -> None:
        # {hex(normalized): (x, y)} — toạ độ anchor (mét).
        self.beacons: Dict[str, Tuple[float, float]] = {
            _normalize_hex(h): (float(p[0]), float(p[1])) for h, p in beacon_positions.items()
        }
        self.dist_bank = DistanceKalmanFilterBank()
        self.pos_kf = ConstantVelocityKF()
        self._last_pos: Optional[Tuple[float, float]] = None

    # ------------------------------------------------------------------
    def process_ranges(
        self, raw_distances_cm: Dict[str, float], dt: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Nạp tập range thô (cm) của 1 nhịp. Trả trạng thái vị trí hoặc None."""
        filtered_m: Dict[str, float] = {}
        variances: Dict[str, float] = {}

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
            if USE_DISTANCE_KALMAN:
                f = self.dist_bank.filter(h, d_m)
                if f is None:
                    continue
                filtered_m[h] = float(f)
                variances[h] = self.dist_bank.variance(h)
            else:
                filtered_m[h] = d_m
                variances[h] = 1.0

        if len(filtered_m) < MIN_BEACONS:
            return None

        prior_weights = None
        if USE_WLS_PRIOR and variances:
            inv = {h: 1.0 / max(v, 1e-3) for h, v in variances.items()}
            mean_w = sum(inv.values()) / len(inv)
            if mean_w > 0:
                prior_weights = {h: w / mean_w for h, w in inv.items()}

        solved = solve_trilateration_robust(
            self.beacons,
            filtered_m,
            prior_weights=prior_weights,
            initial_guess=self._last_pos if WARM_START else None,
        )
        if not solved:
            return None

        raw_x, raw_y = float(solved["x"]), float(solved["y"])
        P = solved["P"]
        self._last_pos = (raw_x, raw_y)

        fx, fy = self.pos_kf.update([raw_x, raw_y], dt=dt, meas_cov=P)
        vx, vy = self.pos_kf.velocity

        return {
            "x": fx,
            "y": fy,
            "raw_x": raw_x,            # nghiệm hình học trước khi lọc CV
            "raw_y": raw_y,
            "rms_error": float(solved["rms"]),
            "num_beacons": int(solved["num_beacons"]),
            "residuals_m": solved["residuals"],
            "velocity": (vx, vy),
            "filtered_distances_cm": {h: round(d * 100.0, 1) for h, d in filtered_m.items()},
        }

    def reset(self) -> None:
        self.dist_bank.reset()
        self.pos_kf.reset()
        self._last_pos = None
