"""Vẽ biểu đồ phân tích train/val loss sau khi huấn luyện Transformer.

Module này thay thế script draw.py cũ (vốn nằm lạc trong thư mục model và phụ
thuộc seaborn chưa được cài). Thay đổi chính:
- Bỏ phụ thuộc seaborn (dùng style sẵn của matplotlib).
- Ưu tiên đọc `training_history.csv` do train.py sinh ra; nếu không có thì parse
  ngược lại từ file log stdout (tương thích các campaign cũ như map_15).
- Số mẫu train/val/test lấy động từ log thay vì hard-code.
- Sửa boxplot cho matplotlib >= 3.9 (labels -> tick_labels) và thêm guard cho các
  lần train ngắn (ít epoch) để không làm hỏng pipeline tự động.

Tất cả artifact (PNG + CSV) được lưu vào MODEL_SAVE_DIR của map/campaign hiện tại,
giống bố cục thư mục backend/algorithms/transformer/model/map_15/campaign_14/.
"""
from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")  # backend không cần GUI, an toàn khi chạy headless trên server.
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import make_interp_spline
from scipy.stats import gaussian_kde, pearsonr

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.algorithms.transformer import config


def _history_csv_path(model_dir: str) -> str:
    return os.path.join(model_dir, "training_history.csv")


def _find_log_path(model_dir: str) -> Optional[str]:
    """Tìm file log stdout trong model_dir (tên có dạng train_<N>_epochs_stdout.log)."""
    candidates = sorted(Path(model_dir).glob("train_*_epochs_stdout.log"))
    return str(candidates[0]) if candidates else None


def _load_history(model_dir: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Đọc (epochs, train_losses, val_losses) từ CSV hoặc parse log.

    Ưu tiên training_history.csv; nếu thiếu thì parse từ file log stdout.
    """
    csv_path = _history_csv_path(model_dir)
    epochs: List[int] = []
    train_losses: List[float] = []
    val_losses: List[float] = []

    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                epochs.append(int(row["epoch"]))
                train_losses.append(float(row["train_loss"]))
                val_losses.append(float(row["val_loss"]))
    else:
        log_path = _find_log_path(model_dir)
        if log_path is None:
            raise FileNotFoundError(
                f"Không tìm thấy training_history.csv lẫn file log trong {model_dir}. "
                "Hãy chạy train.py trước."
            )
        pattern = re.compile(
            r"Epoch \[(\d+)/\d+\] Train Loss: ([\d.]+) Val Loss: ([\d.]+)"
        )
        with open(log_path, "r", encoding="utf-8") as file:
            for line in file:
                match = pattern.search(line)
                if match:
                    epochs.append(int(match.group(1)))
                    train_losses.append(float(match.group(2)))
                    val_losses.append(float(match.group(3)))

    if not epochs:
        raise ValueError(f"Không đọc được dữ liệu loss nào trong {model_dir}.")

    return (
        np.array(epochs),
        np.array(train_losses, dtype=float),
        np.array(val_losses, dtype=float),
    )


def _parse_dataset_sizes(model_dir: str) -> Dict[str, str]:
    """Lấy số mẫu train/val/test từ dòng 'Dataset: train=.., val=.., test=..' trong log."""
    sizes = {"train": "N/A", "val": "N/A", "test": "N/A"}
    log_path = _find_log_path(model_dir)
    if log_path is None:
        return sizes
    pattern = re.compile(r"train=(\d+),\s*val=(\d+),\s*test=(\d+)")
    with open(log_path, "r", encoding="utf-8") as file:
        for line in file:
            match = pattern.search(line)
            if match:
                sizes = {
                    "train": match.group(1),
                    "val": match.group(2),
                    "test": match.group(3),
                }
                break
    return sizes


def _safe_spline(epochs: np.ndarray, values: np.ndarray) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Nội suy spline; trả None nếu quá ít điểm (make_interp_spline cần k < n)."""
    n = len(epochs)
    if n < 4:
        return None
    try:
        k = min(3, n - 1)
        spline = make_interp_spline(epochs, values, k=k)
        x_smooth = np.linspace(epochs.min(), epochs.max(), 300)
        return x_smooth, spline(x_smooth)
    except Exception:
        return None


def _plot_comprehensive(
    epochs: np.ndarray,
    train_losses: np.ndarray,
    val_losses: np.ndarray,
    correlation: float,
    output_path: str,
) -> None:
    loss_diff = val_losses - train_losses
    plt.figure(figsize=(18, 12))

    # 1. Train & Validation loss theo epoch.
    ax1 = plt.subplot(3, 3, 1)
    ax1.plot(epochs, train_losses, "o-", label="Train Loss", linewidth=2, markersize=4, color="#1f77b4", alpha=0.8)
    ax1.plot(epochs, val_losses, "s-", label="Validation Loss", linewidth=2, markersize=4, color="#ff7f0e", alpha=0.8)
    ax1.set_xlabel("Epoch", fontweight="bold")
    ax1.set_ylabel("Loss", fontweight="bold")
    ax1.set_title("Train vs Validation Loss Over Epochs", fontweight="bold")
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.3)

    # 2. Đường loss làm mượt + vùng gap.
    ax2 = plt.subplot(3, 3, 2)
    train_smooth = _safe_spline(epochs, train_losses)
    val_smooth = _safe_spline(epochs, val_losses)
    if train_smooth is not None and val_smooth is not None:
        ax2.plot(train_smooth[0], train_smooth[1], "-", label="Train (Smoothed)", linewidth=2.5, color="#1f77b4")
        ax2.plot(val_smooth[0], val_smooth[1], "-", label="Validation (Smoothed)", linewidth=2.5, color="#ff7f0e")
        ax2.fill_between(train_smooth[0], train_smooth[1], val_smooth[1], alpha=0.2, color="gray", label="Gap")
    else:
        ax2.plot(epochs, train_losses, "-", label="Train Loss", linewidth=2.5, color="#1f77b4")
        ax2.plot(epochs, val_losses, "-", label="Validation Loss", linewidth=2.5, color="#ff7f0e")
    ax2.set_xlabel("Epoch", fontweight="bold")
    ax2.set_ylabel("Loss", fontweight="bold")
    ax2.set_title("Smoothed Loss Curves with Gap", fontweight="bold")
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.3)

    # 3. Scatter tương quan train vs val.
    ax3 = plt.subplot(3, 3, 3)
    scatter = ax3.scatter(train_losses, val_losses, c=epochs, cmap="viridis", s=50, alpha=0.6, edgecolors="black", linewidth=0.5)
    lo = min(train_losses.min(), val_losses.min())
    hi = max(train_losses.max(), val_losses.max())
    ax3.plot([lo, hi], [lo, hi], "r--", linewidth=2, label="Perfect Correlation")
    ax3.set_xlabel("Train Loss", fontweight="bold")
    ax3.set_ylabel("Validation Loss", fontweight="bold")
    ax3.set_title(f"Train vs Val (Corr: {correlation:.4f})", fontweight="bold")
    ax3.legend(loc="upper left")
    plt.colorbar(scatter, ax=ax3).set_label("Epoch")
    ax3.grid(True, alpha=0.3)

    # 4. Chênh lệch val - train.
    ax4 = plt.subplot(3, 3, 4)
    colors = ["red" if x > 0 else "green" for x in loss_diff]
    ax4.bar(epochs, loss_diff, color=colors, alpha=0.6, edgecolor="black", linewidth=0.5)
    ax4.axhline(y=0, color="black", linewidth=1)
    ax4.set_xlabel("Epoch", fontweight="bold")
    ax4.set_ylabel("Val - Train", fontweight="bold")
    ax4.set_title("Validation-Training Loss Difference", fontweight="bold")
    ax4.grid(True, alpha=0.3, axis="y")

    # 5. Box plot phân phối loss.
    ax5 = plt.subplot(3, 3, 5)
    bp = ax5.boxplot([train_losses, val_losses], tick_labels=["Train", "Val"], patch_artist=True)
    for patch, color in zip(bp["boxes"], ["#1f77b4", "#ff7f0e"]):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax5.set_ylabel("Loss Value", fontweight="bold")
    ax5.set_title("Loss Distribution Comparison", fontweight="bold")
    ax5.grid(True, alpha=0.3, axis="y")

    # 6. Phần trăm chênh lệch.
    ax6 = plt.subplot(3, 3, 6)
    pct_diff = ((val_losses - train_losses) / np.where(train_losses == 0, np.nan, train_losses)) * 100
    ax6.plot(epochs, pct_diff, "o-", linewidth=2, markersize=4, color="#2ca02c", alpha=0.8)
    ax6.axhline(y=0, color="black", linestyle="--", linewidth=1)
    ax6.set_xlabel("Epoch", fontweight="bold")
    ax6.set_ylabel("Percentage Difference (%)", fontweight="bold")
    ax6.set_title("(Val - Train) / Train * 100%", fontweight="bold")
    ax6.grid(True, alpha=0.3)

    # 7. Loss tích lũy.
    ax7 = plt.subplot(3, 3, 7)
    ax7.plot(epochs, np.cumsum(train_losses), "o-", label="Cumulative Train", linewidth=2, markersize=4, color="#1f77b4", alpha=0.8)
    ax7.plot(epochs, np.cumsum(val_losses), "s-", label="Cumulative Val", linewidth=2, markersize=4, color="#ff7f0e", alpha=0.8)
    ax7.set_xlabel("Epoch", fontweight="bold")
    ax7.set_ylabel("Cumulative Loss", fontweight="bold")
    ax7.set_title("Cumulative Loss Over Epochs", fontweight="bold")
    ax7.legend(loc="upper left")
    ax7.grid(True, alpha=0.3)

    # 8. Tốc độ cải thiện loss (âm gradient).
    ax8 = plt.subplot(3, 3, 8)
    ax8.plot(epochs, -np.gradient(train_losses), "o-", label="Train Improvement", linewidth=2, markersize=4, color="#1f77b4", alpha=0.8)
    ax8.plot(epochs, -np.gradient(val_losses), "s-", label="Val Improvement", linewidth=2, markersize=4, color="#ff7f0e", alpha=0.8)
    ax8.axhline(y=0, color="black", linestyle="--", linewidth=1)
    ax8.set_xlabel("Epoch", fontweight="bold")
    ax8.set_ylabel("Improvement Rate", fontweight="bold")
    ax8.set_title("Loss Improvement Rate per Epoch", fontweight="bold")
    ax8.legend(loc="best")
    ax8.grid(True, alpha=0.3)

    # 9. Mật độ 2D.
    ax9 = plt.subplot(3, 3, 9)
    hist = ax9.hist2d(train_losses, val_losses, bins=20, cmap="YlOrRd")
    ax9.set_xlabel("Train Loss", fontweight="bold")
    ax9.set_ylabel("Validation Loss", fontweight="bold")
    ax9.set_title("2D Density Distribution", fontweight="bold")
    plt.colorbar(hist[3], ax=ax9, label="Count")

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def _plot_statistics(
    epochs: np.ndarray,
    train_losses: np.ndarray,
    val_losses: np.ndarray,
    correlation: float,
    p_value: float,
    dataset_sizes: Dict[str, str],
    output_path: str,
) -> None:
    loss_diff = val_losses - train_losses
    _fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1. Histogram.
    ax = axes[0, 0]
    ax.hist(train_losses, bins=15, alpha=0.6, label="Train Loss", color="#1f77b4", edgecolor="black")
    ax.hist(val_losses, bins=15, alpha=0.6, label="Validation Loss", color="#ff7f0e", edgecolor="black")
    ax.set_xlabel("Loss Value", fontweight="bold")
    ax.set_ylabel("Frequency", fontweight="bold")
    ax.set_title("Loss Distribution Histogram", fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    # 2. KDE (guard nếu quá ít điểm hoặc loss hằng số).
    ax = axes[0, 1]
    try:
        kde_train = gaussian_kde(train_losses)
        kde_val = gaussian_kde(val_losses)
        x_range = np.linspace(min(train_losses.min(), val_losses.min()), max(train_losses.max(), val_losses.max()), 200)
        ax.plot(x_range, kde_train(x_range), linewidth=2.5, label="Train KDE", color="#1f77b4")
        ax.plot(x_range, kde_val(x_range), linewidth=2.5, label="Val KDE", color="#ff7f0e")
        ax.fill_between(x_range, kde_train(x_range), alpha=0.3, color="#1f77b4")
        ax.fill_between(x_range, kde_val(x_range), alpha=0.3, color="#ff7f0e")
        ax.legend()
    except Exception:
        ax.text(0.5, 0.5, "KDE cần nhiều điểm hơn", ha="center", va="center", transform=ax.transAxes)
    ax.set_xlabel("Loss Value", fontweight="bold")
    ax.set_ylabel("Density", fontweight="bold")
    ax.set_title("Kernel Density Estimation", fontweight="bold")
    ax.grid(True, alpha=0.3)

    # 3. Loss trung bình theo 3 phase.
    ax = axes[1, 0]
    n = len(epochs)
    p1, p2 = n // 3, 2 * n // 3
    phases = ["Phase 1\n(Early)", "Phase 2\n(Mid)", "Phase 3\n(Late)"]
    if n >= 3:
        train_means = [np.mean(train_losses[:p1]), np.mean(train_losses[p1:p2]), np.mean(train_losses[p2:])]
        val_means = [np.mean(val_losses[:p1]), np.mean(val_losses[p1:p2]), np.mean(val_losses[p2:])]
    else:
        train_means = [np.mean(train_losses)] * 3
        val_means = [np.mean(val_losses)] * 3
    x_pos = np.arange(len(phases))
    width = 0.35
    ax.bar(x_pos - width / 2, train_means, width, label="Train Loss", color="#1f77b4", alpha=0.7, edgecolor="black")
    ax.bar(x_pos + width / 2, val_means, width, label="Val Loss", color="#ff7f0e", alpha=0.7, edgecolor="black")
    ax.set_ylabel("Average Loss", fontweight="bold")
    ax.set_title("Average Loss by Training Phase", fontweight="bold")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(phases)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    # 4. Hộp text thống kê.
    ax = axes[1, 1]
    ax.axis("off")
    corr_label = "Strong" if abs(correlation) > 0.8 else "Moderate" if abs(correlation) > 0.5 else "Weak"
    stats_text = f"""
TRAINING STATISTICS
{'='*50}

Dataset Information:
  - Total Epochs: {len(epochs)}
  - Training Samples: {dataset_sizes['train']}
  - Validation Samples: {dataset_sizes['val']}
  - Test Samples: {dataset_sizes['test']}

Train Loss Statistics:
  - Mean: {np.mean(train_losses):.6f}
  - Std Dev: {np.std(train_losses):.6f}
  - Min: {np.min(train_losses):.6f} (Epoch {epochs[np.argmin(train_losses)]})
  - Max: {np.max(train_losses):.6f} (Epoch {epochs[np.argmax(train_losses)]})

Validation Loss Statistics:
  - Mean: {np.mean(val_losses):.6f}
  - Std Dev: {np.std(val_losses):.6f}
  - Min: {np.min(val_losses):.6f} (Epoch {epochs[np.argmin(val_losses)]})
  - Max: {np.max(val_losses):.6f} (Epoch {epochs[np.argmax(val_losses)]})

Loss Difference (Val - Train):
  - Mean Diff: {np.mean(loss_diff):.6f}
  - Std Dev Diff: {np.std(loss_diff):.6f}

Correlation Analysis:
  - Pearson Correlation: {correlation:.6f}
  - P-value: {p_value:.2e}
  - Interpretation: {corr_label} correlation

Model Quality Indicators:
  - Overfitting Indicator (Avg Val-Train): {np.mean(loss_diff):.6f}
  - Final Train Loss: {train_losses[-1]:.6f}
  - Final Val Loss: {val_losses[-1]:.6f}
  - Best Val Loss: {np.min(val_losses):.6f} (Epoch {epochs[np.argmin(val_losses)]})
"""
    ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=9.5, verticalalignment="top", fontfamily="monospace", bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.3))

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def _export_csv(epochs: np.ndarray, train_losses: np.ndarray, val_losses: np.ndarray, output_path: str) -> None:
    """Xuất loss_data.csv (giữ tương thích định dạng cũ của map_15)."""
    loss_diff = val_losses - train_losses
    with open(output_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Epoch", "Train_Loss", "Val_Loss", "Loss_Diff", "Val_minus_Train_Pct"])
        for i in range(len(epochs)):
            pct = ((val_losses[i] - train_losses[i]) / train_losses[i] * 100) if train_losses[i] != 0 else 0.0
            writer.writerow([epochs[i], train_losses[i], val_losses[i], loss_diff[i], pct])


def generate_plots(model_dir: Optional[str] = None) -> None:
    """Sinh toàn bộ biểu đồ + CSV phân tích loss vào model_dir.

    Args:
        model_dir: Thư mục model/map/campaign. Mặc định lấy từ config.MODEL_SAVE_DIR.
    """
    model_dir = model_dir or config.MODEL_SAVE_DIR
    os.makedirs(model_dir, exist_ok=True)

    epochs, train_losses, val_losses = _load_history(model_dir)

    if len(epochs) >= 2:
        correlation, p_value = pearsonr(train_losses, val_losses)
    else:
        correlation, p_value = float("nan"), float("nan")
    dataset_sizes = _parse_dataset_sizes(model_dir)

    comprehensive_path = os.path.join(model_dir, "loss_analysis_comprehensive.png")
    statistics_path = os.path.join(model_dir, "loss_statistics.png")
    csv_path = os.path.join(model_dir, "loss_data.csv")

    _plot_comprehensive(epochs, train_losses, val_losses, correlation, comprehensive_path)
    _plot_statistics(epochs, train_losses, val_losses, correlation, p_value, dataset_sizes, statistics_path)
    _export_csv(epochs, train_losses, val_losses, csv_path)

    print("\nVisualization artifacts saved:")
    print(f"- {comprehensive_path}")
    print(f"- {statistics_path}")
    print(f"- {csv_path}")


if __name__ == "__main__":
    from backend.algorithms.transformer.training.preprocess import _enable_utf8_console

    _enable_utf8_console()
    generate_plots()
