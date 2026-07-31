"""Training loop for the RSSI Transformer regression model.

File này là entrypoint độc lập cho quá trình huấn luyện Transformer. Nó không
phụ thuộc vào FastAPI server đang chạy; dữ liệu được lấy trực tiếp từ MySQL
qua pipeline trong dataset.py.
"""
from __future__ import annotations

import os
import sys
import csv
from pathlib import Path
from typing import List, Optional, TextIO, Tuple
import argparse

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.algorithms.transformer import config
from backend.algorithms.transformer.training.dataset import create_dataloaders
from backend.algorithms.transformer.training.model_def import RSSITransformer


def _select_device() -> torch.device:
    """Tự động chọn device tốt nhất đang có.

    Thứ tự ưu tiên:
    1. CUDA nếu máy có GPU NVIDIA và PyTorch build hỗ trợ CUDA.
    2. MPS nếu chạy trên Apple Silicon.
    3. CPU nếu không có accelerator.
    """
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _set_random_seed(seed: int) -> None:
    """Cố định seed để kết quả train dễ tái lập hơn giữa các lần chạy."""
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _checkpoint_path() -> str:
    return os.path.join(config.MODEL_SAVE_DIR, "transformer_model.pt")


class _TeeLogger:
    """Ghi đồng thời ra console và file log để mọi lần train đều có log artifact.

    Trước đây train.py chỉ print() ra terminal nên log chỉ tồn tại nếu người dùng
    tự redirect ">". Đó là lý do campaign map_17 không có file log. Logger này gắn
    trực tiếp vào pipeline nên log luôn được lưu trong MODEL_SAVE_DIR.
    """

    def __init__(self, log_path: str) -> None:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        self._handle: TextIO = open(log_path, "w", encoding="utf-8")
        self.log_path = log_path

    def log(self, message: str = "") -> None:
        print(message)
        self._handle.write(message + "\n")
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()


def _save_history_csv(history: List[dict], csv_path: str) -> None:
    """Lưu lịch sử train/val loss từng epoch ra CSV để vẽ biểu đồ về sau."""
    if not history:
        return
    with open(csv_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file, fieldnames=["epoch", "train_loss", "val_loss", "is_best"]
        )
        writer.writeheader()
        writer.writerows(history)


def _run_training_epoch(
    model: nn.Module,
    train_loader: DataLoader,
    criterion: nn.Module,
    optimizer: optim.Optimizer,
    device: torch.device,
) -> float:
    """Chạy một epoch training và trả về MSE trung bình theo số mẫu.

    MSELoss đo sai số bình phương giữa tọa độ dự đoán và tọa độ thật:
        loss = mean((x_pred - x_true)^2 + (y_pred - y_true)^2)

    Trong phase train, ta bật model.train() để Dropout hoạt động và mọi tensor
    trung gian được lưu lại cho quá trình lan truyền ngược.
    """
    model.train()
    running_loss = 0.0
    sample_count = 0

    for X_batch, y_batch in train_loader:
        X_batch = X_batch.to(device)
        y_batch = y_batch.to(device)

        # Reset gradient cũ. Nếu không reset, PyTorch sẽ cộng dồn gradient qua batch.
        optimizer.zero_grad()

        # Forward: Transformer biến chuỗi RSSI [B,35,8] thành tọa độ [B,2].
        y_pred = model(X_batch)
        loss = criterion(y_pred, y_batch)

        # Backward: tính đạo hàm dLoss/dWeight cho toàn bộ tham số trainable.
        loss.backward()

        # Optimizer cập nhật trọng số theo gradient vừa tính.
        optimizer.step()

        batch_size = X_batch.size(0)
        running_loss += loss.item() * batch_size
        sample_count += batch_size

    return running_loss / max(sample_count, 1)


def _evaluate(
    model: nn.Module,
    data_loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> float:
    """Đánh giá model mà không tính gradient để tiết kiệm bộ nhớ và thời gian."""
    model.eval()
    running_loss = 0.0
    sample_count = 0

    with torch.no_grad():
        for X_batch, y_batch in data_loader:
            X_batch = X_batch.to(device)
            y_batch = y_batch.to(device)

            y_pred = model(X_batch)
            loss = criterion(y_pred, y_batch)

            batch_size = X_batch.size(0)
            running_loss += loss.item() * batch_size
            sample_count += batch_size

    return running_loss / max(sample_count, 1)


def train_model(num_epochs: Optional[int] = None) -> Tuple[RSSITransformer, float]:
    """Huấn luyện RSSITransformer và lưu checkpoint tốt nhất theo validation loss.

    Cải tiến so với bản cũ:
    - Optimizer AdamW có weight_decay để chống overfit.
    - Early stopping theo patience: dừng sớm khi val loss không cải thiện sau
      EARLY_STOP_PATIENCE epoch (không dùng ngưỡng loss tuyệt đối). Checkpoint
      tốt nhất vẫn luôn được giữ.
    - Tự ghi log ra file + lưu training_history.csv trong MODEL_SAVE_DIR.

    Args:
        num_epochs: Cho phép override số epoch khi smoke test. Nếu None, dùng
            EPOCHS từ config làm TRẦN (early stopping có thể dừng sớm hơn).

    Returns:
        Tuple gồm model sau epoch cuối và best validation loss.
    """
    _set_random_seed(config.RANDOM_SEED)
    device = _select_device()
    epochs = num_epochs if num_epochs is not None else config.EPOCHS

    os.makedirs(config.MODEL_SAVE_DIR, exist_ok=True)
    logger = _TeeLogger(os.path.join(config.MODEL_SAVE_DIR, f"train_{epochs}_epochs_stdout.log"))
    history: List[dict] = []

    try:
        logger.log(f"Device: {device}")
        logger.log(f"Model save dir: {config.MODEL_SAVE_DIR}")
        logger.log(
            f"Optimizer: AdamW(lr={config.LEARNING_RATE}, weight_decay={config.WEIGHT_DECAY}) | "
            f"EarlyStopping(patience={config.EARLY_STOP_PATIENCE}, "
            f"min_delta={config.EARLY_STOP_MIN_DELTA})"
        )

        train_loader, val_loader, _test_loader = create_dataloaders()
        logger.log(
            "Dataset: "
            f"train={len(train_loader.dataset)}, "
            f"val={len(val_loader.dataset)}, "
            f"test={len(_test_loader.dataset)}"
        )

        model = RSSITransformer().to(device)
        criterion = nn.MSELoss()
        optimizer = optim.AdamW(
            model.parameters(),
            lr=config.LEARNING_RATE,
            weight_decay=config.WEIGHT_DECAY,
        )

        best_val_loss = float("inf")
        epochs_without_improvement = 0
        best_epoch = 0
        checkpoint_path = _checkpoint_path()

        for epoch in range(1, epochs + 1):
            train_loss = _run_training_epoch(
                model=model,
                train_loader=train_loader,
                criterion=criterion,
                optimizer=optimizer,
                device=device,
            )
            val_loss = _evaluate(
                model=model,
                data_loader=val_loader,
                criterion=criterion,
                device=device,
            )

            logger.log(
                f"Epoch [{epoch:03d}/{epochs:03d}] "
                f"Train Loss: {train_loss:.6f} "
                f"Val Loss: {val_loss:.6f}"
            )

            is_best = val_loss < best_val_loss - config.EARLY_STOP_MIN_DELTA
            if is_best:
                best_val_loss = val_loss
                best_epoch = epoch
                epochs_without_improvement = 0
                torch.save(model.state_dict(), checkpoint_path)
                logger.log(f"  Best checkpoint saved: {checkpoint_path}")
            else:
                epochs_without_improvement += 1

            history.append(
                {
                    "epoch": epoch,
                    "train_loss": f"{train_loss:.6f}",
                    "val_loss": f"{val_loss:.6f}",
                    "is_best": int(is_best),
                }
            )

            if epochs_without_improvement >= config.EARLY_STOP_PATIENCE:
                logger.log(
                    f"Early stopping tại epoch {epoch}: val loss không cải thiện "
                    f"trong {config.EARLY_STOP_PATIENCE} epoch liên tiếp."
                )
                break

        logger.log(
            f"Training complete. Best Val Loss: {best_val_loss:.6f} (epoch {best_epoch})"
        )
        return model, best_val_loss
    finally:
        _save_history_csv(history, os.path.join(config.MODEL_SAVE_DIR, "training_history.csv"))
        logger.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the RSSI Transformer regression model."
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=None,
        help="Override config.EPOCHS for smoke tests or short experiments.",
    )
    parser.add_argument(
        "--no-eval",
        action="store_true",
        help="Bỏ qua bước tự động chạy evaluate.py sau khi train xong.",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Bỏ qua bước tự động vẽ biểu đồ loss sau khi train xong.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    from backend.algorithms.transformer.training.preprocess import _enable_utf8_console

    _enable_utf8_console()
    args = _parse_args()
    train_model(num_epochs=args.epochs)

    # Tự động evaluate sau khi train để mọi campaign luôn có evaluation_metrics.json
    # và các báo cáo sai số (đây là nguyên nhân gốc khiến map_17 thiếu artifact).
    if not args.no_eval:
        try:
            from backend.algorithms.transformer.training.evaluate import evaluate_model

            print("\n=== Auto-evaluation on test split ===")
            evaluate_model()
        except Exception as exc:  # noqa: BLE001 - không để eval lỗi làm hỏng train
            print(f"[warn] Auto-evaluation bị bỏ qua do lỗi: {exc}")

    # Tự động vẽ biểu đồ phân tích loss từ training_history.csv.
    if not args.no_plot:
        try:
            from backend.algorithms.transformer.training.visualize import generate_plots

            print("\n=== Auto-visualization of loss curves ===")
            generate_plots()
        except Exception as exc:  # noqa: BLE001 - không để vẽ lỗi làm hỏng train
            print(f"[warn] Auto-visualization bị bỏ qua do lỗi: {exc}")
