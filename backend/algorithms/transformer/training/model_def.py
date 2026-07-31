"""Transformer Encoder model for RSSI sequence-to-vector regression.

Mô hình nhận một batch cửa sổ RSSI có shape [Batch, Window, 8] và dự đoán
tọa độ tuyệt đối [x, y]. Kiến trúc chỉ dùng Transformer Encoder vì bài toán
không cần sinh chuỗi đầu ra.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import torch
from torch import nn

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.algorithms.transformer import config


class PositionalEncoding(nn.Module):
    """Mã hóa vị trí bằng sin/cos cho chuỗi RSSI.

    Self-Attention tự thân là một phép toán gần như không phụ thuộc thứ tự:
    nếu ta tráo vị trí các token, dot-product attention vẫn chỉ nhìn thấy tập
    vector đặc trưng mà không biết token nào đến trước token nào. Với RSSI,
    thứ tự 35 mẫu trong cửa sổ là thông tin quan trọng vì nó biểu diễn dao
    động theo thời gian của nhiễu multipath và zero-order hold.

    Positional Encoding thêm vào mỗi timestamp một vector tất định:
        PE(pos, 2i)     = sin(pos / 10000^(2i / d_model))
        PE(pos, 2i + 1) = cos(pos / 10000^(2i / d_model))

    Các tần số sin/cos khác nhau cho phép model phân biệt vị trí ngắn hạn và
    dài hạn trong cùng cửa sổ. Ma trận này không cần học, vì vậy dùng
    register_buffer để lưu cùng device với model nhưng không cập nhật gradient.
    """

    def __init__(self, d_model: int, max_len: int, dropout: float) -> None:
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        position = torch.arange(max_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float32)
            * (-math.log(10000.0) / d_model)
        )

        pe = torch.zeros(max_len, d_model, dtype=torch.float32)
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term[: pe[:, 1::2].shape[1]])

        # batch_first=True trong toàn pipeline nên pe có shape [1, Window, D].
        # Khi cộng với input [Batch, Window, D], PyTorch broadcast theo Batch.
        self.register_buffer("pe", pe.unsqueeze(0), persistent=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Cộng thông tin vị trí vào embedding.

        Args:
            x: Tensor shape [Batch, Window, D_MODEL].

        Returns:
            Tensor cùng shape, đã cộng positional encoding và dropout.
        """
        if x.dim() != 3:
            raise ValueError(f"Expected input shape [batch, window, d_model], got {tuple(x.shape)}")

        window_size = x.size(1)
        if window_size > self.pe.size(1):
            raise ValueError(
                f"Input window_size={window_size} exceeds positional encoding max_len={self.pe.size(1)}"
            )

        x = x + self.pe[:, :window_size, :]
        return self.dropout(x)


class RSSITransformer(nn.Module):
    """Transformer Encoder cho bài toán RSSI fingerprint regression.

    Luồng toán học chính:
    1. Input embedding: biến vector RSSI 8 chiều thành vector đặc trưng 64 chiều.
    2. Positional encoding: thêm thông tin thứ tự thời gian trong cửa sổ.
    3. Transformer Encoder: dùng multi-head self-attention để so sánh từng
       timestamp RSSI với các timestamp còn lại trong cùng cửa sổ.
    4. Mean pooling: gom toàn bộ chuỗi thành một vector ổn định.
    5. Regression head: ánh xạ vector đặc trưng sang tọa độ [x, y].
    """

    def __init__(self) -> None:
        super().__init__()
        self._validate_config()

        # Khối 1: Input Embedding.
        # RSSI sau scaler chỉ có 8 kênh nên không gian biểu diễn ban đầu quá nhỏ.
        # Linear projection học phép chiếu W*x+b để đưa mỗi timestamp lên D_MODEL,
        # tạo đủ chiều cho các attention head học các kiểu tương quan khác nhau.
        self.input_embedding = nn.Linear(config.INPUT_DIM, config.D_MODEL)

        # Khối 2: Positional Encoding.
        # Cộng vector vị trí vào embedding để Encoder phân biệt nhịp RSSI thứ 1,
        # thứ 2, ..., thứ 35 trong cùng cửa sổ.
        self.positional_encoding = PositionalEncoding(
            d_model=config.D_MODEL,
            max_len=config.WINDOW_SIZE,
            dropout=config.DROPOUT,
        )

        # Khối 3: Transformer Encoder.
        # Multi-Head Self-Attention tạo Q, K, V từ chính chuỗi input:
        # Attention(Q,K,V)=softmax(QK^T/sqrt(d_k))V.
        # N_HEADS chia D_MODEL thành nhiều không gian con để model đồng thời học
        # nhiều dạng quan hệ RSSI: nhiễu ngắn hạn, beacon ổn định, mẫu lặp ZOH...
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.D_MODEL,
            nhead=config.N_HEADS,
            dim_feedforward=config.D_MODEL * 4,
            dropout=config.DROPOUT,
            batch_first=True,
            activation="relu",
        )
        self.encoder = nn.TransformerEncoder(
            encoder_layer=encoder_layer,
            num_layers=config.NUM_LAYERS,
        )

        # Khối 4: Regression Head.
        # Mean pooling lấy trung bình theo trục thời gian để biến [B,W,D] -> [B,D].
        # Về mặt vật lý, tọa độ của một cửa sổ fingerprint tĩnh phải ổn định;
        # lấy trung bình giúp model dùng toàn bộ 1 giây RSSI thay vì phụ thuộc
        # vào token cuối cùng vốn có thể là mẫu bị nhiễu hoặc giá trị lặp.
        self.regression_head = nn.Sequential(
            nn.Linear(config.D_MODEL, config.D_MODEL // 2),
            nn.ReLU(),
            nn.Linear(config.D_MODEL // 2, config.OUTPUT_DIM),
        )

    @staticmethod
    def _validate_config() -> None:
        if config.D_MODEL % config.N_HEADS != 0:
            raise ValueError("D_MODEL must be divisible by N_HEADS for multi-head attention")
        if config.INPUT_DIM != 8:
            raise ValueError("INPUT_DIM must remain 8 for 4 Wi-Fi RSSI + 4 BLE RSSI")
        if config.OUTPUT_DIM != 2:
            raise ValueError("OUTPUT_DIM must be 2 for [x, y] regression")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Chạy forward pass.

        Args:
            x: Tensor shape [Batch, WINDOW_SIZE, INPUT_DIM].

        Returns:
            Tensor shape [Batch, OUTPUT_DIM] tương ứng tọa độ [x, y].
        """
        if x.dim() != 3:
            raise ValueError(f"Expected input shape [batch, window, input_dim], got {tuple(x.shape)}")
        if x.size(-1) != config.INPUT_DIM:
            raise ValueError(f"Expected input_dim={config.INPUT_DIM}, got {x.size(-1)}")

        x = self.input_embedding(x)
        x = self.positional_encoding(x)
        x = self.encoder(x)

        pooled = x.mean(dim=1)
        return self.regression_head(pooled)


def count_trainable_parameters(model: nn.Module) -> int:
    """Đếm số tham số có gradient để kiểm soát độ nặng của model."""
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)


if __name__ == "__main__":
    model = RSSITransformer()
    dummy_input = torch.randn(config.BATCH_SIZE, config.WINDOW_SIZE, config.INPUT_DIM)
    output = model(dummy_input)

    print(f"Output shape: {output.shape}")
    print(f"Trainable parameters: {count_trainable_parameters(model):,}")
