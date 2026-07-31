"""Configuration for the Error-State Kalman Filter (Khối 3, algorithm 3)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ESKFConfig:
    """Tham số ESKF fuse observation Transformer + motion PDR (xem reference.txt)."""

    # Measurement noise của Transformer (độ lệch chuẩn, mét). LẤY TỪ sai số thật
    # trên map_17 (mean ~1.206 m). TUYỆT ĐỐI không dùng 0.42 (số rò rỉ cũ).
    R_MEAS_M: float = 1.2

    # Độ bất định vị trí khởi tạo (mét) cho P0 = diag(std^2, std^2).
    INITIAL_POSITION_STD_M: float = 3.0

    # Sàn cho độ lệch chuẩn quá trình mỗi bước (mét) — tránh Q quá nhỏ làm filter
    # quá "cứng" rồi bỏ qua observation.
    MIN_PROCESS_STD_M: float = 0.05

    # Ngưỡng Mahalanobis (chi-square 2 DoF) để loại outlier observation (nhảy NLOS).
    # 9.21 ≈ 99%, 5.99 ≈ 95%. Đặt None để TẮT gating.
    GATING_THRESHOLD: float = 9.21

    # Dự phòng khi PDR không cấp sigma: sigma_step = ratio * step_length.
    FALLBACK_STEP_RATIO: float = 0.15
    FALLBACK_HEADING_DEG: float = 3.0


CONFIG = ESKFConfig()

R_MEAS_M = CONFIG.R_MEAS_M
INITIAL_POSITION_STD_M = CONFIG.INITIAL_POSITION_STD_M
MIN_PROCESS_STD_M = CONFIG.MIN_PROCESS_STD_M
GATING_THRESHOLD = CONFIG.GATING_THRESHOLD
FALLBACK_STEP_RATIO = CONFIG.FALLBACK_STEP_RATIO
FALLBACK_HEADING_DEG = CONFIG.FALLBACK_HEADING_DEG
