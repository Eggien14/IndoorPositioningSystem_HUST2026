"""Central configuration for Transformer RSSI fingerprint training.

File này chỉ chứa tham số cấu hình. Training runtime và server runtime
sẽ import cùng một nguồn cấu hình để tránh lệch tham số giữa các giai đoạn.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TransformerConfig:
    """Cấu hình tập trung cho model Transformer của algorithm 3."""

    # Cấu hình dữ liệu trong database hiện tại.
    MAP_ID: int = 17
    CAMPAIGN_ID: int = 21
    SAMPLES_PER_CELL: int = 500

    # Cấu hình xử lý RSSI.
    # Dải RSSI hợp lệ thực tế của phần cứng: [-99, -1] dBm. Mọi mẫu có bất kỳ
    # kênh RSSI nào null/NaN hoặc nằm NGOÀI dải này (ví dụ <= -100 do mất tín
    # hiệu, hoặc giá trị dương do lỗi cảm biến) đều bị LOẠI BỎ hoàn toàn — không
    # điền sentinel, không nạp vào model. Đây là nguồn chân lý chung cho cả
    # training (preprocess) lẫn runtime/test để tránh lệch hành vi.
    RSSI_VALID_MIN: int = -99
    RSSI_VALID_MAX: int = -1
    # Giữ lại để tương thích tham chiếu cũ; không còn dùng để điền sentinel.
    NULL_RSSI_VALUE: int = -100

    # Cửa sổ thời gian: 35 mẫu tương đương khoảng 1 giây ở tốc độ MQTT 35Hz.
    WINDOW_SIZE: int = 35
    STEP_SIZE: int = 5

    # Training hyperparameters.
    BATCH_SIZE: int = 64
    TRAIN_RATIO: float = 0.70
    VAL_RATIO: float = 0.15
    TEST_RATIO: float = 0.15
    LEARNING_RATE: float = 0.001
    EPOCHS: int = 100
    RANDOM_SEED: int = 42

    # Regularization & early stopping (chống overfit + tiết kiệm thời gian train).
    # WEIGHT_DECAY: hệ số L2 cho AdamW.
    # EARLY_STOP_PATIENCE: số epoch liên tiếp val loss không cải thiện thì dừng sớm.
    # EARLY_STOP_MIN_DELTA: mức cải thiện tối thiểu mới được tính là "tốt hơn".
    WEIGHT_DECAY: float = 1e-4
    EARLY_STOP_PATIENCE: int = 12
    EARLY_STOP_MIN_DELTA: float = 1e-4

    # Chiến lược chia dữ liệu. "temporal": chia theo thời gian thu trong từng cell
    # (train = mẫu thu trước, test = mẫu thu sau) để tránh rò rỉ dữ liệu giữa các
    # window gần như trùng nhau. Đây là cách đánh giá trung thực hơn random split.
    SPLIT_STRATEGY: str = "temporal"

    # Transformer architecture.
    INPUT_DIM: int = 8
    D_MODEL: int = 64
    N_HEADS: int = 4
    NUM_LAYERS: int = 2
    OUTPUT_DIM: int = 2
    DROPOUT: float = 0.1

    @property
    def TRANSFORMER_DIR(self) -> Path:
        return Path(__file__).resolve().parent

    @property
    def MODEL_SAVE_DIR(self) -> str:
        return str(
            self.TRANSFORMER_DIR
            / "model"
            / f"map_{self.MAP_ID}"
            / f"campaign_{self.CAMPAIGN_ID}"
        )

    @property
    def SCALER_PATH(self) -> str:
        return str(Path(self.MODEL_SAVE_DIR) / "scaler.joblib")


CONFIG = TransformerConfig()

# Module-level aliases để các file training/runtime có thể import ngắn gọn.
MAP_ID = CONFIG.MAP_ID
CAMPAIGN_ID = CONFIG.CAMPAIGN_ID
SAMPLES_PER_CELL = CONFIG.SAMPLES_PER_CELL
RSSI_VALID_MIN = CONFIG.RSSI_VALID_MIN
RSSI_VALID_MAX = CONFIG.RSSI_VALID_MAX
NULL_RSSI_VALUE = CONFIG.NULL_RSSI_VALUE
WINDOW_SIZE = CONFIG.WINDOW_SIZE
STEP_SIZE = CONFIG.STEP_SIZE
BATCH_SIZE = CONFIG.BATCH_SIZE
TRAIN_RATIO = CONFIG.TRAIN_RATIO
VAL_RATIO = CONFIG.VAL_RATIO
TEST_RATIO = CONFIG.TEST_RATIO
LEARNING_RATE = CONFIG.LEARNING_RATE
EPOCHS = CONFIG.EPOCHS
RANDOM_SEED = CONFIG.RANDOM_SEED
WEIGHT_DECAY = CONFIG.WEIGHT_DECAY
EARLY_STOP_PATIENCE = CONFIG.EARLY_STOP_PATIENCE
EARLY_STOP_MIN_DELTA = CONFIG.EARLY_STOP_MIN_DELTA
SPLIT_STRATEGY = CONFIG.SPLIT_STRATEGY
INPUT_DIM = CONFIG.INPUT_DIM
D_MODEL = CONFIG.D_MODEL
N_HEADS = CONFIG.N_HEADS
NUM_LAYERS = CONFIG.NUM_LAYERS
OUTPUT_DIM = CONFIG.OUTPUT_DIM
DROPOUT = CONFIG.DROPOUT
MODEL_SAVE_DIR = CONFIG.MODEL_SAVE_DIR
SCALER_PATH = CONFIG.SCALER_PATH
