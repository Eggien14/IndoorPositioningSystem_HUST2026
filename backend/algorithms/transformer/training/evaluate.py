"""Evaluate the best RSSI Transformer checkpoint on the test split.

Trong IPS, MSELoss chỉ là mục tiêu tối ưu toán học. Chỉ số có ý nghĩa vật lý
thực tế là khoảng cách Euclid giữa tọa độ dự đoán và tọa độ thật, tính bằng mét
vì mỗi cell trong map tương ứng 1m x 1m.
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.algorithms.transformer import config
from backend.algorithms.transformer.training.dataset import create_dataloaders
from backend.algorithms.transformer.training.model_def import RSSITransformer


def _select_device() -> torch.device:
    """Chọn device tốt nhất hiện có, tương tự train.py."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _checkpoint_path() -> str:
    return os.path.join(config.MODEL_SAVE_DIR, "transformer_model.pt")


def _load_best_model(device: torch.device) -> RSSITransformer:
    """Khởi tạo model và nạp best checkpoint đã lưu sau training."""
    checkpoint_path = _checkpoint_path()
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(
            f"Checkpoint not found: {checkpoint_path}. Run train.py first."
        )

    model = RSSITransformer().to(device)
    state_dict = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()
    return model


def _collect_predictions(
    model: RSSITransformer,
    test_loader,
    device: torch.device,
) -> Tuple[np.ndarray, np.ndarray]:
    """Chạy inference trên toàn bộ test_loader và gom kết quả về CPU numpy."""
    predictions = []
    ground_truths = []

    with torch.no_grad():
        for X_batch, y_batch in test_loader:
            X_batch = X_batch.to(device)

            y_pred = model(X_batch)
            predictions.append(y_pred.detach().cpu().numpy())
            ground_truths.append(y_batch.detach().cpu().numpy())

    return np.concatenate(predictions, axis=0), np.concatenate(ground_truths, axis=0)


def _calculate_distance_errors(
    predictions: np.ndarray,
    ground_truths: np.ndarray,
) -> np.ndarray:
    """Tính sai số Euclid: sqrt((x_pred-x_true)^2 + (y_pred-y_true)^2)."""
    deltas = predictions - ground_truths
    return np.sqrt(np.sum(np.square(deltas), axis=1))


def _build_error_dataframe(
    predictions: np.ndarray,
    ground_truths: np.ndarray,
    errors_m: np.ndarray,
) -> pd.DataFrame:
    """Tạo bảng chi tiết để group theo tọa độ thật và tìm vùng lỗi cao."""
    return pd.DataFrame(
        {
            "true_x": ground_truths[:, 0],
            "true_y": ground_truths[:, 1],
            "pred_x": predictions[:, 0],
            "pred_y": predictions[:, 1],
            "error_m": errors_m,
        }
    )


def _coordinate_error_summary(report_frame: pd.DataFrame) -> pd.DataFrame:
    """Nhóm theo tọa độ thật để tìm vùng có mean error cao."""
    return (
        report_frame
        .groupby(["true_x", "true_y"], as_index=False)
        .agg(
            samples=("error_m", "size"),
            mean_error_m=("error_m", "mean"),
            median_error_m=("error_m", "median"),
            max_error_m=("error_m", "max"),
        )
        .sort_values("mean_error_m", ascending=False)
    )


def _save_reports(
    metrics: Dict[str, float],
    report_frame: pd.DataFrame,
    coordinate_errors: pd.DataFrame,
) -> None:
    """Lưu báo cáo evaluation vào thư mục model để truy vết kết quả."""
    os.makedirs(config.MODEL_SAVE_DIR, exist_ok=True)

    metrics_path = os.path.join(config.MODEL_SAVE_DIR, "evaluation_metrics.json")
    predictions_path = os.path.join(config.MODEL_SAVE_DIR, "evaluation_predictions.csv")
    coordinate_path = os.path.join(config.MODEL_SAVE_DIR, "evaluation_coordinate_errors.csv")

    with open(metrics_path, "w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2)

    report_frame.to_csv(predictions_path, index=False)
    coordinate_errors.to_csv(coordinate_path, index=False)

    print("\nEvaluation reports saved:")
    print(f"- {metrics_path}")
    print(f"- {predictions_path}")
    print(f"- {coordinate_path}")


def evaluate_model() -> Dict[str, float]:
    """Đánh giá best checkpoint và in báo cáo sai số vật lý bằng mét."""
    device = _select_device()
    print(f"Device: {device}")
    print(f"Checkpoint: {_checkpoint_path()}")

    _, _, test_loader = create_dataloaders()
    model = _load_best_model(device)

    predictions, ground_truths = _collect_predictions(model, test_loader, device)
    errors_m = _calculate_distance_errors(predictions, ground_truths)

    metrics = {
        "mean_error_m": float(np.mean(errors_m)),
        "median_error_m": float(np.median(errors_m)),
        "max_error_m": float(np.max(errors_m)),
        "ce90_m": float(np.percentile(errors_m, 90)),
    }

    print("\nPhysical Error Metrics")
    print(f"Mean Error:   {metrics['mean_error_m']:.3f} m")
    print(f"Median Error: {metrics['median_error_m']:.3f} m")
    print(f"Max Error:    {metrics['max_error_m']:.3f} m")
    print(f"CE90:         {metrics['ce90_m']:.3f} m")

    report_frame = _build_error_dataframe(predictions, ground_truths, errors_m)
    coordinate_errors = _coordinate_error_summary(report_frame)
    top_coordinates = coordinate_errors.head(5)

    print("\nTop 5 Coordinates By Mean Error")
    if top_coordinates.empty:
        print("No coordinate report available.")
    else:
        print(
            top_coordinates.to_string(
                index=False,
                formatters={
                    "true_x": "{:.0f}".format,
                    "true_y": "{:.0f}".format,
                    "mean_error_m": "{:.3f}".format,
                    "median_error_m": "{:.3f}".format,
                    "max_error_m": "{:.3f}".format,
                },
            )
        )

    _save_reports(metrics, report_frame, coordinate_errors)
    return metrics


if __name__ == "__main__":
    from backend.algorithms.transformer.training.preprocess import _enable_utf8_console

    _enable_utf8_console()
    evaluate_model()
