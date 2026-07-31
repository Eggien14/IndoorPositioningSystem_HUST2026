"""Configuration for the Pedestrian Dead Reckoning module (Khối 2, algorithm 3)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PDRConfig:
    """Tập trung các tham số có thể tinh chỉnh của PDR.

    Phát hiện bước kế thừa ý tưởng server cũ (dual-threshold trên gia tốc), nhưng
    bổ sung theo literature: low-pass filter khử nhiễu + step length THÍCH NGHI
    (Weinberg/Kim) thay cho chiều dài bước cố định. Xem reference.txt để biết nguồn.
    """

    # --- Phát hiện bước (dual-threshold peak detection) ---
    # acc_z là gia tốc tuyến tính (đã trừ trọng lực), dao động quanh 0 khi đi bộ.
    UPPER_THRESHOLD: float = 1.0       # ngưỡng đỉnh cao (m/s^2)
    LOWER_THRESHOLD: float = -1.0      # ngưỡng đỉnh thấp (m/s^2)
    MIN_STEP_TIME: int = 100           # ms: khoảng đỉnh-cao -> đỉnh-thấp nhỏ nhất
    MAX_STEP_TIME: int = 600           # ms: lớn nhất

    # --- Low-pass filter gia tốc (khử nhiễu trước khi so ngưỡng) ---
    # First-order IIR (EMA), cutoff theo Hz. Đặt <= 0 để TẮT lọc (passthrough).
    # LƯU Ý (đo thực tế trên test_case_D8): dữ liệu BNO055 của thiết bị này khá sạch
    # (~65 cụm đỉnh rõ ràng), nên cutoff thấp (3–5Hz) triệt tiêu 20–35% bước thật.
    # Default 10Hz = lọc NHẸ (chỉ cắt nhiễu tần số cao), giữ ~85–90% bước. Nên tinh
    # chỉnh lại theo từng thiết bị bằng harness test P1 nếu IMU nhiễu hơn.
    LOWPASS_CUTOFF_HZ: float = 10.0

    # --- Tín hiệu phát hiện ---
    # False: dùng acc_z (mặc định, hợp khi thiết bị giữ hướng ổn định).
    # True : dùng |a| - baseline (bất biến hướng); baseline bám DC bằng EMA.
    USE_ACC_MAGNITUDE: bool = False

    # --- Ước lượng chiều dài bước ---
    # "fixed"    : luôn dùng DEFAULT_STEP_LENGTH.
    # "weinberg" : L = K * (a_max - a_min) ^ 0.25
    # "kim"      : L = K * (mean|a| trong bước) ^ (1/3)
    STEP_LENGTH_MODEL: str = "weinberg"
    DEFAULT_STEP_LENGTH: float = 0.43  # fallback khi "fixed" hoặc dữ liệu thiếu
    # WEINBERG_K hiệu chỉnh từ D8: tổng quãng đường PDR khớp chiều dài quỹ đạo thật
    # (24.41 m). K=0.40 cho overshoot ~21%; D8_1_1 -> 0.331, D8_1_2 -> 0.320 ⇒ chọn 0.33.
    WEINBERG_K: float = 0.33           # đã calib theo người/thiết bị (dữ liệu D8)
    KIM_K: float = 0.40                # mô hình Kim — chưa calib riêng
    MIN_STEP_LENGTH: float = 0.30      # clamp dưới để tránh giá trị rác
    MAX_STEP_LENGTH: float = 1.00      # clamp trên

    # --- Hướng ---
    # Hai mức bù góc (đều trừ khỏi yaw thô):
    #   adjusted_yaw = yaw_raw - DEFAULT_OFFSET_ANGLE - DEFAULT_OFFSET_ANGLE_BNO
    # - DEFAULT_OFFSET_ANGLE: góc lệch của BẢN ĐỒ (từ DB, "clockwise từ true north").
    #   Theo quy ước yaw_map=0 ⇒ đi theo +Oy. Với map 17 có +Oy = West nên offset = -90.
    # - DEFAULT_OFFSET_ANGLE_BNO: bù lỗi CẦM/GẮN cảm biến BNO055, luôn là bội số của
    #   90°. =0 nếu BNO gắn đúng hướng map. Với dữ liệu D8 đo được BNO lệch -90°.
    DEFAULT_OFFSET_ANGLE: float = 0.0
    DEFAULT_OFFSET_ANGLE_BNO: float = 5.0

    # --- Độ bất định (cung cấp cho ma trận nhiễu quá trình Q của ESKF) ---
    PROCESS_NOISE_STEP_RATIO: float = 0.15   # sigma_step = ratio * step_length (m)
    PROCESS_NOISE_HEADING_DEG: float = 3.0   # sigma hướng (độ)


CONFIG = PDRConfig()

# Module-level aliases để runtime import ngắn gọn.
UPPER_THRESHOLD = CONFIG.UPPER_THRESHOLD
LOWER_THRESHOLD = CONFIG.LOWER_THRESHOLD
MIN_STEP_TIME = CONFIG.MIN_STEP_TIME
MAX_STEP_TIME = CONFIG.MAX_STEP_TIME
LOWPASS_CUTOFF_HZ = CONFIG.LOWPASS_CUTOFF_HZ  # noqa: E501 (xem ghi chú trong PDRConfig)
USE_ACC_MAGNITUDE = CONFIG.USE_ACC_MAGNITUDE
STEP_LENGTH_MODEL = CONFIG.STEP_LENGTH_MODEL
DEFAULT_STEP_LENGTH = CONFIG.DEFAULT_STEP_LENGTH
WEINBERG_K = CONFIG.WEINBERG_K
KIM_K = CONFIG.KIM_K
MIN_STEP_LENGTH = CONFIG.MIN_STEP_LENGTH
MAX_STEP_LENGTH = CONFIG.MAX_STEP_LENGTH
DEFAULT_OFFSET_ANGLE = CONFIG.DEFAULT_OFFSET_ANGLE
DEFAULT_OFFSET_ANGLE_BNO = CONFIG.DEFAULT_OFFSET_ANGLE_BNO
PROCESS_NOISE_STEP_RATIO = CONFIG.PROCESS_NOISE_STEP_RATIO
PROCESS_NOISE_HEADING_DEG = CONFIG.PROCESS_NOISE_HEADING_DEG
