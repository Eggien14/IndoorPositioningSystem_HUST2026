"""Error-State Kalman Filter cho fusion vị trí 2D (Khối 3, algorithm 3).

ESKF2D fuse:
- PROCESS (predict): displacement (Δx, Δy) mỗi bước từ PDR (motion model).
- MEASUREMENT (update): tọa độ tuyệt đối (x, y) từ Transformer (observation model).

Với state vị trí thuần [x, y], động học sai số tuyến tính và H = I nên ESKF rút gọn
thành Kalman Filter tuyến tính; ta vẫn giữ đúng khung error-state (predict → update →
inject → reset δx) theo spec và để mở rộng thêm trạng thái hướng sau này.

Xem reference.txt để biết công thức và nguồn tham khảo.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.algorithms.eskf import config


@dataclass
class ESKFState:
    """Trạng thái fused trả ra cho runtime/UI."""

    x: float
    y: float
    pos_std: float        # sqrt(trace(P)/2): độ bất định vị trí trung bình (m)
    step_count: int       # số lần predict (bước PDR) đã nạp
    update_count: int     # số lần update (observation) đã chấp nhận
    rejected_count: int   # số observation bị gating loại


class ESKF2D:
    """Error-State Kalman Filter cho vị trí 2D."""

    def __init__(
        self,
        x0: float,
        y0: float,
        initial_std: float = config.INITIAL_POSITION_STD_M,
        r_meas: float = config.R_MEAS_M,
        gating_threshold: Optional[float] = config.GATING_THRESHOLD,
    ) -> None:
        # Nominal state p = [x, y]^T
        self.p = np.array([float(x0), float(y0)], dtype=float)
        # Covariance P (2x2)
        self.P = np.eye(2, dtype=float) * float(initial_std) ** 2
        self.r_meas = float(r_meas)
        self.gating_threshold = gating_threshold

        self.step_count = 0
        self.update_count = 0
        self.rejected_count = 0

    # ------------------------------------------------------------------
    # PREDICT — nạp displacement của PDR (control input)
    # ------------------------------------------------------------------
    def predict(
        self,
        delta_x: float,
        delta_y: float,
        sigma_step: Optional[float] = None,
        sigma_heading_deg: Optional[float] = None,
        step_length: Optional[float] = None,
    ) -> None:
        """Cập nhật nominal state + covariance theo một bước PDR.

        Q (process noise) suy từ độ bất định bước:
            q^2 = sigma_step^2 + (L * radians(sigma_heading_deg))^2
        Nếu PDR không cấp sigma, dùng fallback từ config theo step_length.
        """
        # Nominal: p += u
        self.p = self.p + np.array([float(delta_x), float(delta_y)], dtype=float)

        # Ước lượng độ dài bước cho thành phần ngang nếu cần.
        if step_length is None:
            step_length = float(math.hypot(delta_x, delta_y))

        if sigma_step is None:
            sigma_step = config.FALLBACK_STEP_RATIO * step_length
        if sigma_heading_deg is None:
            sigma_heading_deg = config.FALLBACK_HEADING_DEG

        lateral = step_length * math.radians(float(sigma_heading_deg))
        q = math.sqrt(float(sigma_step) ** 2 + lateral ** 2)
        q = max(q, config.MIN_PROCESS_STD_M)

        # Covariance: P = F P F^T + Q, với F = I
        self.P = self.P + np.eye(2, dtype=float) * q ** 2
        self.step_count += 1

    # ------------------------------------------------------------------
    # UPDATE — nạp observation tuyệt đối của Transformer
    # ------------------------------------------------------------------
    def update(self, z_x: float, z_y: float, r_meas: Optional[float] = None) -> bool:
        """Hiệu chỉnh state bằng observation (z_x, z_y).

        Trả về True nếu observation được chấp nhận, False nếu bị gating loại
        (coi là nhảy NLOS). H = I (quan sát trực tiếp vị trí).
        """
        r = float(r_meas) if r_meas is not None else self.r_meas
        R = np.eye(2, dtype=float) * r ** 2

        z = np.array([float(z_x), float(z_y)], dtype=float)
        innovation = z - self.p                      # δz = Z_obs - p
        S = self.P + R                               # S = H P H^T + R, H=I

        try:
            S_inv = np.linalg.inv(S)
        except np.linalg.LinAlgError:
            return False

        # Mahalanobis gating: loại observation nhảy bất thường (NLOS).
        if self.gating_threshold is not None:
            mahalanobis_sq = float(innovation.T @ S_inv @ innovation)
            if mahalanobis_sq > self.gating_threshold:
                self.rejected_count += 1
                return False

        # Kalman gain, error estimate, inject, reset.
        K = self.P @ S_inv                           # K = P H^T S^-1
        delta_x_hat = K @ innovation                 # δx̂ = K δz
        self.p = self.p + delta_x_hat                # INJECT
        self.P = (np.eye(2, dtype=float) - K) @ self.P  # (I - K H) P
        # RESET error-state: δx̂ về 0 (ngầm định, không lưu state).
        self.update_count += 1
        return True

    # ------------------------------------------------------------------
    def get_state(self) -> ESKFState:
        pos_std = math.sqrt(float(np.trace(self.P)) / 2.0)
        return ESKFState(
            x=float(self.p[0]),
            y=float(self.p[1]),
            pos_std=pos_std,
            step_count=self.step_count,
            update_count=self.update_count,
            rejected_count=self.rejected_count,
        )

    def position(self) -> Tuple[float, float]:
        return float(self.p[0]), float(self.p[1])


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass

    # Demo: bắt đầu (0,0), PDR đi +x mỗi bước 1m nhưng có bias; Transformer kéo về thật.
    eskf = ESKF2D(x0=0.0, y0=0.0, initial_std=1.0, r_meas=1.0)
    print("start:", eskf.position())
    for k in range(5):
        eskf.predict(delta_x=1.0, delta_y=0.2, sigma_step=0.15, sigma_heading_deg=3.0, step_length=1.0)
        # Observation "thật" đi thẳng +x (y=0), nhiễu nhẹ.
        accepted = eskf.update(z_x=(k + 1) * 1.0, z_y=0.0)
        s = eskf.get_state()
        print(f"step {k+1}: fused=({s.x:.3f},{s.y:.3f}) std={s.pos_std:.3f} accepted={accepted}")
    # Observation nhảy bất thường (NLOS) -> nên bị gating loại.
    rej = eskf.update(z_x=50.0, z_y=50.0)
    print("NLOS jump accepted?", rej, "(False = bị loại đúng)")
