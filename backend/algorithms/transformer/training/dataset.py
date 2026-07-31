"""PyTorch DataLoader creation for Transformer RSSI fingerprint training."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

import torch
from torch.utils.data import DataLoader, TensorDataset

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.algorithms.transformer import config
from backend.algorithms.transformer.training.preprocess import get_split_windows


def _validate_split_ratios() -> None:
    total_ratio = config.TRAIN_RATIO + config.VAL_RATIO + config.TEST_RATIO
    if abs(total_ratio - 1.0) > 1e-6:
        raise ValueError(
            "TRAIN_RATIO + VAL_RATIO + TEST_RATIO must equal 1.0, "
            f"got {total_ratio}"
        )


def _to_tensor_dataset(X, y) -> TensorDataset:
    """Chuyển numpy arrays sang TensorDataset float32 cho PyTorch."""
    X_tensor = torch.as_tensor(X, dtype=torch.float32)
    y_tensor = torch.as_tensor(y, dtype=torch.float32)
    return TensorDataset(X_tensor, y_tensor)


def create_dataloaders() -> Tuple[DataLoader, DataLoader, DataLoader]:
    """Tạo train/val/test DataLoader từ dữ liệu fingerprint đã tiền xử lý.

    Việc chia train/val/test được thực hiện trong preprocess.get_split_windows()
    theo thời gian thu trong từng cell (chống rò rỉ), nên ở đây ta chỉ đóng gói
    các mảng đã chia sẵn thành TensorDataset/DataLoader. Chỉ train_loader shuffle.
    """
    _validate_split_ratios()

    (X_train, y_train), (X_val, y_val), (X_test, y_test) = get_split_windows()

    train_dataset = _to_tensor_dataset(X_train, y_train)
    val_dataset = _to_tensor_dataset(X_val, y_val)
    test_dataset = _to_tensor_dataset(X_test, y_test)

    train_loader = DataLoader(
        train_dataset,
        batch_size=config.BATCH_SIZE,
        shuffle=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=config.BATCH_SIZE,
        shuffle=False,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=config.BATCH_SIZE,
        shuffle=False,
    )

    return train_loader, val_loader, test_loader


if __name__ == "__main__":
    train_loader, val_loader, test_loader = create_dataloaders()
    total_samples = (
        len(train_loader.dataset)
        + len(val_loader.dataset)
        + len(test_loader.dataset)
    )

    first_batch_X, first_batch_y = next(iter(train_loader))
    print(f"Total samples: {total_samples}")
    print(f"Train samples: {len(train_loader.dataset)}")
    print(f"Validation samples: {len(val_loader.dataset)}")
    print(f"Test samples: {len(test_loader.dataset)}")
    print(f"First batch X shape: {list(first_batch_X.shape)}")
    print(f"First batch y shape: {list(first_batch_y.shape)}")
