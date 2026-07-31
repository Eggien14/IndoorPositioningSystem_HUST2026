"""Per-anchor Kalman filtering of raw UWB distance streams.

THAM SỐ TINH CHỈNH ở ĐẦU FILE.

Mô hình: random-walk (constant-position) 1D cho mỗi cặp tag-anchor.
Outlier (NLoS spike) được xử lý ĐÚNG cách (xem reference.txt mục 4):
- Gate theo độ lớn innovation |z - x^-|. Nếu vượt ngưỡng -> KHÔNG nạp measurement
  (giữ prediction, để covariance phình ra), CHỨ KHÔNG "clamp về prediction" (cách cũ
  vừa làm filter quá tự tin, vừa khiến nó dính/trễ và bỏ qua chuyển động thật).
- Nếu bị từ chối liên tiếp >= REACQUIRE_AFTER lần -> coi là range thật sự nhảy bậc
  (người dùng di chuyển nhanh / đổi vị trí) -> RE-ACQUIRE (nhận lại measurement).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

# ----------------------------------------------------------------------------
# THAM SỐ TINH CHỈNH (per-anchor distance Kalman)
# Hướng A (2026-06): nới gate + re-acquire nhanh hơn, Q/R lớn hơn để bám chuyển
# động thật; vẫn giữ P0. Tinh chỉnh lại khi có log UWB thật (xem READ_ME_tri_lm.md).
# ----------------------------------------------------------------------------
# Q: phương sai quá trình (m^2/bước) — cho phép range "trôi" theo chuyển động.
#   TĂNG Q -> prediction phình P^- nhanh hơn, bám range thô khi di chuyển; ít dính
#        vị trí cũ. ĐỔI LẠI: nhiễu LoS nhỏ cũng làm estimate dao động; WLS (1/P) tin
#        anchor kém hơn khi đứng yên.
#   GIẢM Q -> mượt hơn khi đứng yên, lọc spike tốt hơn. ĐỔI LẠI: chuyển động thật bị
#        trễ; dễ kẹt estimate cũ nếu kết hợp gate hẹp.
DEFAULT_PROCESS_VARIANCE = 0.08
# R: phương sai đo (m^2). σ_meas = sqrt(R). σ≈0.26 m -> R≈0.07 (nới so literature
#   σ_LoS≈0.2 m để tin measurement hơn prediction).
#   TĂNG R -> Kalman gain K nhỏ hơn, ít tin từng mẫu thô; mượt, chống spike. ĐỔI LẠI:
#        trễ khi người di chuyển; gate có thể từ chối nhiều hơn (nu lớn so với x^-).
#   GIẢM R -> bám range thô nhanh. ĐỔI LẠI: nhạy NLoS/multipath; estimate giật.
DEFAULT_MEASUREMENT_VARIANCE = 0.07
# P0: bất định khởi tạo (m^2) — chỉ ảnh hưởng vài mẫu đầu sau re-acquire / anchor mới.
#   TĂNG P0 -> vài bước đầu bám raw mạnh. ĐỔI LẠI: khởi động kém ổn định.
#   GIẢM P0 -> khởi động mượt. ĐỔI LẠI: hội tụ chậm sau re-acquire.
DEFAULT_INITIAL_ERROR_VARIANCE = 1.0
# Gate innovation theo MÉT (|z - x^-|). Vượt -> bỏ qua update (giữ prediction).
#   TĂNG gate -> chấp nhận nhảy range lớn hơn (chuyển động thật). ĐỔI LẠI: spike
#        NLoS có thể lọt qua nếu không bị Huber ở tầng LM bắt kịp.
#   GIẢM gate -> lọc outlier chặt. ĐỔI LẠI: chuyển động thật bị coi là outlier, dính
#        estimate cũ cho đến re-acquire (đã gặp khi gate=1.0 m).
DEFAULT_INNOVATION_GATE_M = 2.0
# Số lần bị từ chối liên tiếp thì RE-ACQUIRE (nhận lại z thô, reset P về P0).
#   GIẢM (1-2) -> nhảy về raw nhanh khi di chuyển; anchor đồng bộ hơn. ĐỔI LẠI:
#        spike NLoS ngắn có thể kéo estimate sai 1-2 nhịp trước khi LM/Huber sửa.
#   TĂNG -> chắc chắn hơn trước NLoS. ĐỔI LẠI: trễ lâu hơn khi đổi vị trí thật;
#        các anchor re-acquire lệch nhịp -> geometry LM lẫn cũ/mới.
DEFAULT_REACQUIRE_AFTER = 2


@dataclass
class ScalarKalmanDistanceFilter:
    """Kalman 1D cho 1 luồng khoảng cách (random walk).

    x_k = x_{k-1} + w,  z_k = x_k + v ;  w~N(0,Q), v~N(0,R).
    Prediction: x^- = x_{k-1}; P^- = P_{k-1} + Q.
    Innovation: nu = z - x^-.  Nếu |nu| > gate: BỎ QUA update (giữ x^-, P^-),
      đếm reject; sau REACQUIRE_AFTER lần liên tiếp -> nhận lại (re-init theo z).
    Update (khi qua gate): K = P^- / (P^- + R); x = x^- + K·nu; P = (1-K)·P^-.
    """

    process_variance: float = DEFAULT_PROCESS_VARIANCE
    measurement_variance: float = DEFAULT_MEASUREMENT_VARIANCE
    initial_estimate: Optional[float] = None
    initial_error_variance: float = DEFAULT_INITIAL_ERROR_VARIANCE
    innovation_gate: Optional[float] = DEFAULT_INNOVATION_GATE_M
    reacquire_after: int = DEFAULT_REACQUIRE_AFTER

    estimate: Optional[float] = field(default=None, init=False)
    error_variance: float = field(default=1.0, init=False)
    _reject_streak: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.error_variance = float(self.initial_error_variance)
        if self.initial_estimate is not None:
            self.estimate = float(self.initial_estimate)

    def update(self, measurement: float) -> float:
        measurement = float(measurement)

        if self.estimate is None:
            self.estimate = measurement
            self.error_variance = float(self.initial_error_variance)
            self._reject_streak = 0
            return self.estimate

        # Prediction
        predicted_estimate = self.estimate
        predicted_error = self.error_variance + self.process_variance

        # Gate theo độ lớn innovation
        if self.innovation_gate is not None and abs(measurement - predicted_estimate) > self.innovation_gate:
            self._reject_streak += 1
            if self._reject_streak >= self.reacquire_after:
                # range nhảy bậc thật -> nhận lại
                self.estimate = measurement
                self.error_variance = float(self.initial_error_variance)
                self._reject_streak = 0
                return self.estimate
            # bỏ qua update: giữ prediction, để covariance phình ra
            self.estimate = predicted_estimate
            self.error_variance = predicted_error
            return self.estimate

        # Update bình thường
        self._reject_streak = 0
        kalman_gain = predicted_error / (predicted_error + self.measurement_variance)
        self.estimate = predicted_estimate + kalman_gain * (measurement - predicted_estimate)
        self.error_variance = (1.0 - kalman_gain) * predicted_error
        return self.estimate

    def reset(self) -> None:
        self.estimate = None
        self.error_variance = float(self.initial_error_variance)
        self._reject_streak = 0


@dataclass
class DistanceKalmanFilterBank:
    """Một ScalarKalmanDistanceFilter cho mỗi anchor id (bank chéo độc lập)."""

    process_variance: float = DEFAULT_PROCESS_VARIANCE
    measurement_variance: float = DEFAULT_MEASUREMENT_VARIANCE
    initial_error_variance: float = DEFAULT_INITIAL_ERROR_VARIANCE
    innovation_gate: Optional[float] = DEFAULT_INNOVATION_GATE_M
    reacquire_after: int = DEFAULT_REACQUIRE_AFTER
    filters: Dict[str, ScalarKalmanDistanceFilter] = field(default_factory=dict)

    def get_filter(self, beacon_hex_id: str) -> ScalarKalmanDistanceFilter:
        filter_instance = self.filters.get(beacon_hex_id)
        if filter_instance is None:
            filter_instance = ScalarKalmanDistanceFilter(
                process_variance=self.process_variance,
                measurement_variance=self.measurement_variance,
                initial_error_variance=self.initial_error_variance,
                innovation_gate=self.innovation_gate,
                reacquire_after=self.reacquire_after,
            )
            self.filters[beacon_hex_id] = filter_instance
        return filter_instance

    def filter(self, beacon_hex_id: str, measured_distance_m: float) -> Optional[float]:
        if measured_distance_m is None:
            return None
        try:
            measurement = float(measured_distance_m)
        except (TypeError, ValueError):
            return None
        if measurement <= 0:
            return None
        return self.get_filter(beacon_hex_id).update(measurement)

    def variance(self, beacon_hex_id: str) -> float:
        """Phương sai ước lượng hiện tại của 1 anchor (để đặt trọng số WLS nếu cần)."""
        f = self.filters.get(beacon_hex_id)
        return float(f.error_variance) if f else float(self.initial_error_variance)

    def reset(self, beacon_hex_id: Optional[str] = None) -> None:
        if beacon_hex_id is None:
            self.filters.clear()
            return
        self.filters.pop(beacon_hex_id, None)

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        return {
            beacon_hex_id: {
                "estimate": float(f.estimate) if f.estimate is not None else None,
                "error_variance": float(f.error_variance),
            }
            for beacon_hex_id, f in self.filters.items()
        }
