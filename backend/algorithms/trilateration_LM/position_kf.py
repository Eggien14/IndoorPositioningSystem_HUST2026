"""Bộ lọc vị trí cuối — Constant-Velocity (CV) linear Kalman filter.

THAM SỐ TINH CHỈNH ở ĐẦU FILE.

State = [x, y, vx, vy] (mô hình vận tốc hằng — white-noise-acceleration).
Measurement = (x, y) do tầng LS hình học cho ra => H TUYẾN TÍNH => KF tuyến tính là
ĐỦ, KHÔNG cần EKF (loosely-coupled; xem reference.txt mục 5).

R thích nghi (tuỳ chọn): R = (CV_RANGE_STD_M^2) · P_geom với P_geom = (J^T W J)^-1 do
solver trả về — fix ở vùng hình học xấu (GDOP lớn) sẽ ÍT được tin hơn.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

# ----------------------------------------------------------------------------
# THAM SỐ TINH CHỈNH (CV position KF)
# ----------------------------------------------------------------------------
CV_PROCESS_PSD = 1.5            # q: mật độ phổ gia tốc (m^2/s^3). Lớn -> bám nhanh, kém mượt.
CV_RANGE_STD_M = 0.20          # σ range (m) để quy P_geom -> covariance vị trí.
CV_MEAS_STD_FLOOR_M = 0.08     # chặn dưới độ lệch chuẩn đo (m)
CV_MEAS_STD_CEIL_M = 1.50      # chặn trên độ lệch chuẩn đo (m)
CV_INIT_POS_VAR = 4.0          # P0 vị trí (m^2)
CV_INIT_VEL_VAR = 1.0          # P0 vận tốc (m^2/s^2)
CV_MAX_DT_S = 1.0              # chặn dt (giây) để tránh nhảy lớn khi mất nhịp
CV_DEFAULT_DT_S = 0.1          # dt mặc định khi không cấp


class ConstantVelocityKF:
    def __init__(self) -> None:
        self.x: Optional[np.ndarray] = None         # [x, y, vx, vy]
        self.P: Optional[np.ndarray] = None
        self._H = np.array([[1.0, 0, 0, 0], [0, 1.0, 0, 0]])

    def _Q(self, dt: float) -> np.ndarray:
        q = CV_PROCESS_PSD
        dt2, dt3, dt4 = dt * dt, dt ** 3, dt ** 4
        return q * np.array([
            [dt4 / 4, 0,       dt3 / 2, 0],
            [0,       dt4 / 4, 0,       dt3 / 2],
            [dt3 / 2, 0,       dt2,     0],
            [0,       dt3 / 2, 0,       dt2],
        ])

    def _meas_R(self, meas_cov: Optional[np.ndarray]) -> np.ndarray:
        floor_v, ceil_v = CV_MEAS_STD_FLOOR_M ** 2, CV_MEAS_STD_CEIL_M ** 2
        if meas_cov is not None:
            R = (CV_RANGE_STD_M ** 2) * np.asarray(meas_cov, dtype=float)
            if R.shape != (2, 2) or not np.all(np.isfinite(R)):
                R = (CV_RANGE_STD_M ** 2) * np.eye(2)
        else:
            R = (CV_RANGE_STD_M ** 2) * np.eye(2)
        # Chặn phương sai trên đường chéo vào [floor, ceil].
        for i in (0, 1):
            R[i, i] = float(min(max(R[i, i], floor_v), ceil_v))
        return R

    def update(self, z_xy, dt: Optional[float] = None, meas_cov: Optional[np.ndarray] = None):
        """Nạp 1 vị trí đo (x,y). Trả (x, y) đã lọc."""
        z = np.asarray(z_xy, dtype=float).reshape(2)

        if self.x is None:
            self.x = np.array([z[0], z[1], 0.0, 0.0])
            self.P = np.diag([CV_INIT_POS_VAR, CV_INIT_POS_VAR, CV_INIT_VEL_VAR, CV_INIT_VEL_VAR])
            return float(self.x[0]), float(self.x[1])

        d = CV_DEFAULT_DT_S if (dt is None or dt <= 0) else min(float(dt), CV_MAX_DT_S)
        F = np.array([[1, 0, d, 0], [0, 1, 0, d], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=float)

        # Predict
        x_pred = F @ self.x
        P_pred = F @ self.P @ F.T + self._Q(d)

        # Update
        R = self._meas_R(meas_cov)
        H = self._H
        innovation = z - H @ x_pred
        S = H @ P_pred @ H.T + R
        K = P_pred @ H.T @ np.linalg.inv(S)
        self.x = x_pred + K @ innovation
        self.P = (np.eye(4) - K @ H) @ P_pred
        return float(self.x[0]), float(self.x[1])

    @property
    def velocity(self):
        if self.x is None:
            return 0.0, 0.0
        return float(self.x[2]), float(self.x[3])

    def reset(self) -> None:
        self.x = None
        self.P = None
