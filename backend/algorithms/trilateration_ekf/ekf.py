"""TrilaterationEKF — tightly-coupled EKF trên range thô (Algorithm 5).

THAM SỐ TINH CHỈNH ở ĐẦU FILE.

State x = [px, py, vx, vy] (constant-velocity).
Predict: F (CV) + Q (white-noise-acceleration), theo dt.
Update: cho TỪNG anchor có range hợp lệ, đo phi tuyến
    h_i(x) = || p - a_i ||,  H_i = [ (px-ax)/h, (py-ay)/h, 0, 0 ]
cập nhật tuần tự (sequential scalar update). Robust theo Mahalanobis/NIS:
    nis = innov^2 / S ;  nis > GATE -> BỎ range ;  HUBER < nis <= GATE -> phình R.
Khởi tạo vị trí bằng LLS (dùng lại engine.lls_initial_position) từ tập range đầu.

Ưu điểm so với loosely-coupled: dùng đo thô (không mất thông tin qua bước LS), và
vẫn cập nhật được khi <3 anchor (sau khi đã khởi tạo).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.algorithms.trilateration_LM.engine import lls_initial_position

# ----------------------------------------------------------------------------
# THAM SỐ TINH CHỈNH (Trilateration EKF)
# ----------------------------------------------------------------------------
EKF_PROCESS_PSD = 1.5          # q: mật độ phổ gia tốc (m^2/s^3)
EKF_RANGE_STD_M = 0.20         # σ đo range (m) -> R = σ^2 mỗi range
EKF_GATE_NIS = 9.0             # NIS > ngưỡng -> loại range (NLoS spike). χ²₁ ~ α nhỏ.
EKF_HUBER_NIS = 4.0           # HUBER < NIS <= GATE -> phình R = R·(NIS/HUBER) (robust)
EKF_INIT_POS_VAR = 4.0         # P0 vị trí (m^2)
EKF_INIT_VEL_VAR = 1.0         # P0 vận tốc (m^2/s^2)
EKF_MAX_DT_S = 1.0
EKF_DEFAULT_DT_S = 0.1
EKF_MIN_BEACONS_INIT = 3       # cần >=3 anchor để KHỞI TẠO (sau đó cập nhật được với ít hơn)


class TrilaterationEKF:
    def __init__(self) -> None:
        self.x: Optional[np.ndarray] = None     # [px, py, vx, vy]
        self.P: Optional[np.ndarray] = None
        self.last_accepted = 0
        self.last_rejected = 0

    # ------------------------------------------------------------------
    def _Q(self, dt: float) -> np.ndarray:
        q = EKF_PROCESS_PSD
        dt2, dt3, dt4 = dt * dt, dt ** 3, dt ** 4
        return q * np.array([
            [dt4 / 4, 0,       dt3 / 2, 0],
            [0,       dt4 / 4, 0,       dt3 / 2],
            [dt3 / 2, 0,       dt2,     0],
            [0,       dt3 / 2, 0,       dt2],
        ])

    def _init_from_ranges(self, beacon_positions: Dict[str, Tuple[float, float]],
                          distances_m: Dict[str, float]) -> bool:
        pts, ds = [], []
        for hex_id, d in distances_m.items():
            a = beacon_positions.get(hex_id)
            if not a or d is None or d <= 0:
                continue
            pts.append((float(a[0]), float(a[1])))
            ds.append(float(d))
        if len(pts) < EKF_MIN_BEACONS_INIT:
            return False
        seed = lls_initial_position(np.asarray(pts, dtype=float), np.asarray(ds, dtype=float))
        if seed is None:
            seed = np.mean(np.asarray(pts, dtype=float), axis=0)
        self.x = np.array([seed[0], seed[1], 0.0, 0.0], dtype=float)
        self.P = np.diag([EKF_INIT_POS_VAR, EKF_INIT_POS_VAR, EKF_INIT_VEL_VAR, EKF_INIT_VEL_VAR])
        return True

    def predict(self, dt: float) -> None:
        d = EKF_DEFAULT_DT_S if (dt is None or dt <= 0) else min(float(dt), EKF_MAX_DT_S)
        F = np.array([[1, 0, d, 0], [0, 1, 0, d], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=float)
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + self._Q(d)

    def update_ranges(self, beacon_positions: Dict[str, Tuple[float, float]],
                      distances_m: Dict[str, float]) -> Tuple[int, int]:
        accepted, rejected = 0, 0
        R = EKF_RANGE_STD_M ** 2
        I4 = np.eye(4)
        for hex_id, d in distances_m.items():
            a = beacon_positions.get(hex_id)
            if not a or d is None or d <= 0:
                continue
            ax, ay = float(a[0]), float(a[1])
            dx, dy = self.x[0] - ax, self.x[1] - ay
            h = max(float(np.hypot(dx, dy)), 1e-6)
            H = np.array([[dx / h, dy / h, 0.0, 0.0]])
            innov = float(d) - h
            S = float(H @ self.P @ H.T) + R
            nis = innov * innov / S
            if nis > EKF_GATE_NIS:
                rejected += 1
                continue
            r_eff = R * (nis / EKF_HUBER_NIS) if nis > EKF_HUBER_NIS else R
            S = float(H @ self.P @ H.T) + r_eff
            K = (self.P @ H.T) / S                 # (4,1)
            self.x = self.x + (K.flatten() * innov)
            self.P = (I4 - K @ H) @ self.P
            accepted += 1
        return accepted, rejected

    def step(self, beacon_positions: Dict[str, Tuple[float, float]],
             distances_m: Dict[str, float], dt: Optional[float] = None) -> Optional[Tuple[float, float]]:
        """Một nhịp: (khởi tạo nếu cần) -> predict -> update. Trả (x, y) hoặc None."""
        if self.x is None:
            if not self._init_from_ranges(beacon_positions, distances_m):
                return None
            self.last_accepted, self.last_rejected = len(distances_m), 0
            return float(self.x[0]), float(self.x[1])

        self.predict(dt)
        self.last_accepted, self.last_rejected = self.update_ranges(beacon_positions, distances_m)
        return float(self.x[0]), float(self.x[1])

    @property
    def velocity(self) -> Tuple[float, float]:
        if self.x is None:
            return 0.0, 0.0
        return float(self.x[2]), float(self.x[3])

    def reset(self) -> None:
        self.x = None
        self.P = None
        self.last_accepted = 0
        self.last_rejected = 0
