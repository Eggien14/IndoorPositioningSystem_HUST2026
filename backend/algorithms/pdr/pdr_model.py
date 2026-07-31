"""Streaming Pedestrian Dead Reckoning model (Khối 2, algorithm 3).

PDRModel nhận IMU theo thời gian thực và xuất một StepEvent cho mỗi bước chân hợp lệ:
vector dịch chuyển (Δx, Δy), chiều dài bước ước lượng, hướng, và độ bất định để khối
ESKF dùng làm process model. Class này KHÔNG lưu tọa độ tuyệt đối của người dùng;
việc cộng dồn vị trí thuộc trách nhiệm của ESKF/runtime phía sau.

Nâng cấp so với bản port từ server cũ (xem reference.txt):
- Low-pass filter (IIR bậc 1) khử nhiễu gia tốc trước khi phát hiện đỉnh.
- Chiều dài bước THÍCH NGHI theo biên độ gia tốc (Weinberg/Kim), thay vì cố định.
- Tùy chọn dùng độ lớn gia tốc |a| (bất biến hướng) thay cho riêng acc_z.
- Xuất sigma_step / sigma_heading cho ma trận nhiễu quá trình Q của ESKF.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.algorithms.pdr import config


@dataclass
class StepEvent:
    """Kết quả của một bước chân hợp lệ — đầu vào process model cho ESKF."""

    timestamp: float          # ms, thời điểm xác nhận bước
    delta_x: float            # dịch chuyển theo Ox (Đông), mét
    delta_y: float            # dịch chuyển theo Oy (Bắc), mét
    step_length: float        # chiều dài bước ước lượng, mét
    heading_deg: float        # hướng map đã bù offset, độ
    sigma_step: float         # độ lệch chuẩn chiều dài bước (cho Q của ESKF)
    sigma_heading_deg: float  # độ lệch chuẩn hướng, độ (cho Q của ESKF)
    step_index: int           # số thứ tự bước kể từ lần reset gần nhất


class _LowPassFilter:
    """Low-pass IIR bậc 1 (EMA) theo cutoff Hz, hỗ trợ dt thay đổi.

    alpha = dt / (RC + dt), với RC = 1 / (2*pi*cutoff). Nếu cutoff <= 0 thì tắt
    lọc (trả nguyên giá trị). Thiết kế streaming: chỉ giữ 1 giá trị trạng thái.
    """

    def __init__(self, cutoff_hz: float) -> None:
        self.cutoff_hz = float(cutoff_hz)
        self._value: Optional[float] = None
        self._last_timestamp_ms: Optional[float] = None

    def reset(self) -> None:
        self._value = None
        self._last_timestamp_ms = None

    def filter(self, x: float, timestamp_ms: float) -> float:
        if self.cutoff_hz <= 0.0:
            return x
        if self._value is None or self._last_timestamp_ms is None:
            self._value = x
            self._last_timestamp_ms = timestamp_ms
            return x

        dt = (timestamp_ms - self._last_timestamp_ms) / 1000.0
        self._last_timestamp_ms = timestamp_ms
        if dt <= 0.0:
            return self._value

        rc = 1.0 / (2.0 * math.pi * self.cutoff_hz)
        alpha = dt / (rc + dt)
        self._value = self._value + alpha * (x - self._value)
        return self._value


class PDRModel:
    """Dual-threshold PDR step detector + adaptive step-length + step vector.

    Finite-state machine:
    - Trạng thái 1: chưa có đỉnh cao, đợi `signal > UPPER_THRESHOLD`.
    - Trạng thái 2: đã có đỉnh cao, tích lũy a_max/a_min/mean|a| và đợi
      `signal < LOWER_THRESHOLD`.
    - Nếu khoảng thời gian high->low nằm trong [MIN_STEP_TIME, MAX_STEP_TIME] thì
      xác nhận bước, ước lượng chiều dài bước, xuất StepEvent.

    `signal` là acc_z (mặc định) hoặc |a| đã trừ baseline (nếu use_acc_magnitude).
    """

    # Baseline tracker (chỉ dùng cho chế độ magnitude) bám thành phần DC của |a|.
    _BASELINE_ALPHA = 0.02

    def __init__(
        self,
        offset_angle: float = config.DEFAULT_OFFSET_ANGLE,
        step_length: float = config.DEFAULT_STEP_LENGTH,
        step_length_model: str = config.STEP_LENGTH_MODEL,
        lowpass_cutoff_hz: float = config.LOWPASS_CUTOFF_HZ,
        use_acc_magnitude: bool = config.USE_ACC_MAGNITUDE,
        offset_angle_bno: float = config.DEFAULT_OFFSET_ANGLE_BNO,
    ) -> None:
        self.offset_angle = float(offset_angle)            # góc lệch bản đồ (từ DB)
        self.offset_angle_bno = float(offset_angle_bno)    # bù lỗi gắn BNO (bội số 90°)
        self.step_length = float(step_length)  # fallback khi model="fixed"
        self.step_length_model = str(step_length_model).lower()
        self.use_acc_magnitude = bool(use_acc_magnitude)

        self._lowpass = _LowPassFilter(lowpass_cutoff_hz)
        self._baseline: Optional[float] = None

        self.last_high_peak_time: float = 0.0
        self.is_waiting_for_low: bool = False
        self.step_count: int = 0

        # Tích lũy biên độ trong một bước để ước lượng chiều dài bước.
        self._step_acc_max: float = 0.0
        self._step_acc_min: float = 0.0
        self._step_abs_sum: float = 0.0
        self._step_sample_count: int = 0

    def reset(self) -> None:
        """Reset trạng thái detector, giữ nguyên cấu hình offset/step length."""
        self.last_high_peak_time = 0.0
        self.is_waiting_for_low = False
        self.step_count = 0
        self._lowpass.reset()
        self._baseline = None
        self._reset_step_accumulators()

    def _reset_step_accumulators(self) -> None:
        self._step_acc_max = 0.0
        self._step_acc_min = 0.0
        self._step_abs_sum = 0.0
        self._step_sample_count = 0

    def _detection_signal(
        self,
        acc_z: float,
        acc_x: Optional[float],
        acc_y: Optional[float],
    ) -> Optional[float]:
        """Tính tín hiệu phát hiện bước (acc_z hoặc |a|-baseline), trả None nếu thiếu."""
        if not self.use_acc_magnitude:
            return acc_z

        if acc_x is None or acc_y is None:
            return None
        magnitude = math.sqrt(acc_x * acc_x + acc_y * acc_y + acc_z * acc_z)
        # Bám DC của |a| bằng EMA chậm rồi trừ đi để tín hiệu dao động quanh 0.
        if self._baseline is None:
            self._baseline = magnitude
        else:
            self._baseline += self._BASELINE_ALPHA * (magnitude - self._baseline)
        return magnitude - self._baseline

    def process_imu_stream(
        self,
        acc_z: float,
        yaw: float,
        timestamp: float,
        acc_x: Optional[float] = None,
        acc_y: Optional[float] = None,
    ) -> Optional[StepEvent]:
        """Xử lý một mẫu IMU; trả StepEvent nếu phát hiện bước, None nếu không.

        Args:
            acc_z: Gia tốc trục đứng tuyến tính (đã trừ trọng lực), m/s^2.
            yaw: Heading/Yaw của BNO055, độ.
            timestamp: Thời gian mẫu, ms.
            acc_x, acc_y: Hai trục còn lại — chỉ cần khi use_acc_magnitude=True.
        """
        acc_z = float(acc_z)
        yaw = float(yaw)
        timestamp = float(timestamp)

        if not (np.isfinite(acc_z) and np.isfinite(yaw) and np.isfinite(timestamp)):
            return None

        raw_signal = self._detection_signal(acc_z, acc_x, acc_y)
        if raw_signal is None or not np.isfinite(raw_signal):
            return None

        signal = self._lowpass.filter(raw_signal, timestamp)

        # Trạng thái 1 -> 2: ghi nhận đỉnh cao, bắt đầu tích lũy biên độ của bước.
        if signal > config.UPPER_THRESHOLD and not self.is_waiting_for_low:
            self.last_high_peak_time = timestamp
            self.is_waiting_for_low = True
            self._step_acc_max = signal
            self._step_acc_min = signal
            self._step_abs_sum = abs(signal)
            self._step_sample_count = 1
            return None

        if self.is_waiting_for_low:
            # Tích lũy biên độ mỗi mẫu trong bước (gồm cả mẫu đỉnh thấp).
            self._step_acc_max = max(self._step_acc_max, signal)
            self._step_acc_min = min(self._step_acc_min, signal)
            self._step_abs_sum += abs(signal)
            self._step_sample_count += 1

            delta_t = timestamp - self.last_high_peak_time

            if signal < config.LOWER_THRESHOLD and config.MIN_STEP_TIME <= delta_t <= config.MAX_STEP_TIME:
                self.is_waiting_for_low = False
                self.step_count += 1
                step_length = self._estimate_step_length()
                event = self._build_step_event(yaw, step_length, timestamp)
                self._reset_step_accumulators()
                return event

            if delta_t > config.MAX_STEP_TIME:
                self.is_waiting_for_low = False
                self._reset_step_accumulators()

        return None

    def _estimate_step_length(self) -> float:
        """Ước lượng chiều dài bước theo model cấu hình, có clamp về dải hợp lý."""
        model = self.step_length_model

        if model == "weinberg":
            amplitude = self._step_acc_max - self._step_acc_min
            if amplitude > 0.0:
                length = config.WEINBERG_K * (amplitude ** 0.25)
            else:
                length = self.step_length
        elif model == "kim":
            if self._step_sample_count > 0:
                mean_abs = self._step_abs_sum / self._step_sample_count
                length = config.KIM_K * (mean_abs ** (1.0 / 3.0)) if mean_abs > 0.0 else self.step_length
            else:
                length = self.step_length
        else:  # "fixed" hoặc giá trị không hợp lệ -> fallback cố định
            length = self.step_length

        return float(min(max(length, config.MIN_STEP_LENGTH), config.MAX_STEP_LENGTH))

    def _build_step_event(self, yaw: float, step_length: float, timestamp: float) -> StepEvent:
        # Trừ cả góc lệch bản đồ lẫn góc lệch gắn BNO khỏi yaw thô.
        adjusted_yaw = yaw - self.offset_angle - self.offset_angle_bno
        delta_x, delta_y = self.compute_step_vector(adjusted_yaw, step_length)
        return StepEvent(
            timestamp=timestamp,
            delta_x=delta_x,
            delta_y=delta_y,
            step_length=step_length,
            heading_deg=adjusted_yaw % 360.0,
            sigma_step=config.PROCESS_NOISE_STEP_RATIO * step_length,
            sigma_heading_deg=config.PROCESS_NOISE_HEADING_DEG,
            step_index=self.step_count,
        )

    @staticmethod
    def compute_step_vector(adjusted_yaw_deg: float, step_length: float) -> tuple[float, float]:
        """Chiếu vector bước lên mặt phẳng map (Ox=Đông/phải, Oy=Bắc/lên).

            delta_x = L * sin(adjusted_yaw)
            delta_y = L * cos(adjusted_yaw)
        """
        radian = math.radians(adjusted_yaw_deg)
        delta_x = step_length * math.sin(radian)
        delta_y = step_length * math.cos(radian)
        return float(delta_x), float(delta_y)


if __name__ == "__main__":
    # Demo tắt low-pass filter để dữ liệu giả với đỉnh đơn-mẫu vẫn vượt ngưỡng.
    # (Dữ liệu thật ở 35Hz có đỉnh kéo dài nhiều mẫu nên LPF không triệt tiêu.)
    model = PDRModel(offset_angle=90.0, step_length_model="weinberg", lowpass_cutoff_hz=0.0)

    mock_data = [
        (0.10, 90.0, 0),
        (1.20, 90.0, 100),
        (0.20, 90.0, 180),
        (-1.25, 90.0, 260),    # bước 1 xác nhận
        (0.05, 90.0, 420),
        (1.15, 135.0, 760),
        (0.10, 135.0, 840),
        (-1.30, 135.0, 930),   # bước 2 xác nhận
        (1.10, 180.0, 1700),
        (-1.20, 180.0, 2405),  # quá MAX_STEP_TIME nên bị hủy
    ]

    for acc_z, yaw, timestamp in mock_data:
        event = model.process_imu_stream(acc_z, yaw, timestamp)
        if event is not None:
            print(
                f"Step {event.step_index}: t={event.timestamp:.0f}ms "
                f"L={event.step_length:.3f}m heading={event.heading_deg:.1f} "
                f"dx={event.delta_x:.4f} dy={event.delta_y:.4f} "
                f"sigma_step={event.sigma_step:.3f}"
            )
