"""Data preprocessing for Transformer RSSI fingerprint training.

Luồng xử lý:
1. Đọc dữ liệu fingerprint từ MySQL theo map/campaign trong config.
2. Làm sạch 8 kênh RSSI Wi-Fi/BLE.
3. Fit MinMaxScaler và lưu scaler vào thư mục model tương ứng map/campaign.
4. Tạo sliding window theo từng cell_id, không cho window vắt ngang cell.
5. Trả về X [N, WINDOW_SIZE, 8] và y [N, 2].
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, Tuple

import joblib
import mysql.connector
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from mysql.connector import Error
from sklearn.preprocessing import MinMaxScaler

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.algorithms.transformer import config


RSSI_COLUMNS = [
    "wifi_rssi_1",
    "wifi_rssi_2",
    "wifi_rssi_3",
    "wifi_rssi_4",
    "ble_rssi_1",
    "ble_rssi_2",
    "ble_rssi_3",
    "ble_rssi_4",
]

LABEL_COLUMNS = ["coord_x", "coord_y"]


class DataPreprocessingError(RuntimeError):
    """Lỗi có ngữ cảnh rõ ràng khi chuẩn bị dữ liệu training thất bại."""


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_env() -> None:
    env_path = _project_root() / ".env"
    load_dotenv(dotenv_path=env_path if env_path.exists() else None)


def _get_db_config() -> dict:
    """Đọc cấu hình MySQL từ .env, không phụ thuộc vào FastAPI server."""
    _load_env()
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "indoor_positioning_db"),
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
    }


def _connect_mysql():
    try:
        return mysql.connector.connect(**_get_db_config())
    except Error as exc:
        raise DataPreprocessingError(f"Cannot connect to MySQL: {exc}") from exc


def fetch_fingerprint_dataframe() -> pd.DataFrame:
    """Trích xuất dữ liệu fingerprint đã thu cho map/campaign hiện tại."""
    query = """
        SELECT
            fd.fingerprint_id,
            fd.cell_id,
            fd.wifi_rssi_1,
            fd.wifi_rssi_2,
            fd.wifi_rssi_3,
            fd.wifi_rssi_4,
            fd.ble_rssi_1,
            fd.ble_rssi_2,
            fd.ble_rssi_3,
            fd.ble_rssi_4,
            fd.collected_at,
            mc.coord_x,
            mc.coord_y
        FROM fingerprint_data AS fd
        INNER JOIN map_cells AS mc
            ON fd.cell_id = mc.cell_id
        WHERE fd.campaign_id = %s
          AND mc.map_id = %s
        ORDER BY fd.cell_id ASC, fd.collected_at ASC, fd.fingerprint_id ASC
    """

    connection = _connect_mysql()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (config.CAMPAIGN_ID, config.MAP_ID))
        dataframe = pd.DataFrame(cursor.fetchall())
    except Exception as exc:
        raise DataPreprocessingError(f"Cannot fetch fingerprint data: {exc}") from exc
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()

    if dataframe.empty:
        raise DataPreprocessingError(
            f"No fingerprint data found for map_id={config.MAP_ID}, "
            f"campaign_id={config.CAMPAIGN_ID}"
        )

    return dataframe


def _drop_invalid_rssi_rows(dataframe: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Loại bỏ hoàn toàn các mẫu có RSSI ngoài dải hợp lệ, thay vì điền sentinel.

    RSSI hợp lệ thực tế nằm trong [RSSI_VALID_MIN, RSSI_VALID_MAX] = [-99, -1] dBm.
    Một mẫu bị coi là KHÔNG hợp lệ nếu BẤT KỲ kênh RSSI nào trong 8 kênh:
      - là NULL/NaN trong database, HOẶC
      - < RSSI_VALID_MIN (ví dụ <= -100: mất tín hiệu), HOẶC
      - > RSSI_VALID_MAX (ví dụ giá trị dương: lỗi cảm biến).

    Trước đây pipeline điền các giá trị này bằng -100 rồi đưa vào model — cách đó
    trộn lẫn tín hiệu thật với tín hiệu lỗi và làm MinMaxScaler bị méo. Theo quy tắc
    vận hành thống nhất, ta loại hẳn: chỉ giữ mẫu có đủ 8 kênh RSSI nằm trong dải
    hợp lệ. Runtime/test cũng áp đúng quy tắc này (xem test/transformer/test_model.py).

    Returns:
        (dataframe đã lọc, số dòng bị loại bỏ).
    """
    cleaned = dataframe.copy()
    for column in RSSI_COLUMNS:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    valid_mask = np.ones(len(cleaned), dtype=bool)
    for column in RSSI_COLUMNS:
        values = cleaned[column].to_numpy()
        valid_mask &= cleaned[column].notna().to_numpy()
        valid_mask &= (values >= config.RSSI_VALID_MIN)
        valid_mask &= (values <= config.RSSI_VALID_MAX)

    dropped_count = int((~valid_mask).sum())
    cleaned = cleaned.loc[valid_mask].reset_index(drop=True)

    if cleaned.empty:
        raise DataPreprocessingError(
            "Toàn bộ mẫu đều ngoài dải RSSI hợp lệ sau khi lọc. "
            f"Kiểm tra dải [{config.RSSI_VALID_MIN}, {config.RSSI_VALID_MAX}] và chất "
            f"lượng dữ liệu map_id={config.MAP_ID}, campaign_id={config.CAMPAIGN_ID}."
        )

    return cleaned, dropped_count


def _split_by_time_per_cell(
    dataframe: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Chia train/val/test theo THỜI GIAN thu trong từng cell (chống rò rỉ).

    dataframe đã được sort theo (cell_id, collected_at) nên trong mỗi cell, các
    mẫu thu TRƯỚC nằm đầu, thu SAU nằm cuối. Ta cắt 3 đoạn liên tiếp:
      [0 : n_train)              -> train (mẫu thu sớm nhất)
      [n_train : n_train+n_val)  -> val
      [n_train+n_val : ]         -> test  (mẫu thu muộn nhất)

    Vì 3 đoạn KHÔNG chồng thời gian, window dựng riêng trong từng đoạn cũng không
    chồng nhau giữa các split -> loại bỏ rò rỉ do window trùng (vốn làm sai số
    đánh giá lạc quan giả tạo khi dùng random shuffle).
    """
    train_parts, val_parts, test_parts = [], [], []

    for _cell_id, group in dataframe.groupby("cell_id", sort=False):
        n = len(group)
        n_train = int(n * config.TRAIN_RATIO)
        n_val = int(n * config.VAL_RATIO)

        train_parts.append(group.iloc[:n_train])
        val_parts.append(group.iloc[n_train : n_train + n_val])
        test_parts.append(group.iloc[n_train + n_val :])

    def _concat(parts):
        if not parts:
            return dataframe.iloc[0:0].copy()
        return pd.concat(parts, axis=0).reset_index(drop=True)

    return _concat(train_parts), _concat(val_parts), _concat(test_parts)


def _sort_by_cell_time(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Sort riêng theo cell_id và thời gian thu mẫu để giữ thứ tự tĩnh trong cell."""
    sorted_frame = dataframe.copy()
    sorted_frame["collected_at"] = pd.to_datetime(sorted_frame["collected_at"])
    return sorted_frame.sort_values(
        by=["cell_id", "collected_at", "fingerprint_id"],
        kind="mergesort",
    ).reset_index(drop=True)


def _fit_and_save_scaler(train_features: pd.DataFrame) -> MinMaxScaler:
    """Fit scaler CHỈ trên 8 kênh RSSI của tập TRAIN và lưu artifact cho runtime.

    Trước đây scaler được fit trên toàn bộ dữ liệu (gồm cả val/test) -> rò rỉ
    thống kê. Giờ scaler chỉ thấy phân phối của train, đúng chuẩn đánh giá trung
    thực. Runtime server sau này load đúng scaler này (tuyệt đối không fit lại).
    """
    scaler = MinMaxScaler()
    scaler.fit(train_features)

    os.makedirs(config.MODEL_SAVE_DIR, exist_ok=True)
    joblib.dump(scaler, config.SCALER_PATH)
    return scaler


def _transform_rssi(dataframe: pd.DataFrame, scaler: MinMaxScaler) -> pd.DataFrame:
    """Áp scaler đã fit trên train lên một split bất kỳ."""
    transformed = dataframe.copy()
    transformed[RSSI_COLUMNS] = scaler.transform(transformed[RSSI_COLUMNS])
    return transformed


def _build_windows(
    dataframe: pd.DataFrame,
    feature_columns: Iterable[str],
    split_name: str,
) -> Tuple[np.ndarray, np.ndarray]:
    """Tạo sliding window theo từng cell, tuyệt đối không trộn cell khác nhau."""
    windows = []
    labels = []

    for _cell_id, group in dataframe.groupby("cell_id", sort=False):
        feature_values = group[list(feature_columns)].to_numpy(dtype=np.float32)
        label_values = group[LABEL_COLUMNS].to_numpy(dtype=np.float32)

        if len(group) < config.WINDOW_SIZE:
            continue

        # Với fingerprint tĩnh, label của mọi dòng trong cùng cell phải giống nhau.
        # Ta dùng label ở đầu window để giữ mapping trực tiếp với cell hiện tại.
        for start_index in range(0, len(group) - config.WINDOW_SIZE + 1, config.STEP_SIZE):
            end_index = start_index + config.WINDOW_SIZE
            windows.append(feature_values[start_index:end_index])
            labels.append(label_values[start_index])

    if not windows:
        raise DataPreprocessingError(
            f"Không tạo được window nào cho split '{split_name}'. "
            f"Kiểm tra WINDOW_SIZE={config.WINDOW_SIZE} và số mẫu hợp lệ mỗi cell "
            f"sau khi loại mẫu mất tín hiệu (mỗi cell cần >= WINDOW_SIZE mẫu trong split)."
        )

    return np.asarray(windows, dtype=np.float32), np.asarray(labels, dtype=np.float32)


def get_split_windows() -> Tuple[
    Tuple[np.ndarray, np.ndarray],
    Tuple[np.ndarray, np.ndarray],
    Tuple[np.ndarray, np.ndarray],
]:
    """Hàm chính cho training: trả về 3 cặp (X, y) cho train/val/test.

    Khác với phiên bản cũ (trả X,y rồi để dataset.py random-split), hàm này tự
    chia theo thời gian trong từng cell, fit scaler chỉ trên train, rồi dựng
    window riêng cho từng split -> không rò rỉ dữ liệu giữa các split.

    Returns:
        ((X_train, y_train), (X_val, y_val), (X_test, y_test)) với X [N, 35, 8],
        y [N, 2].
    """
    dataframe = fetch_fingerprint_dataframe()
    dataframe = _sort_by_cell_time(dataframe)

    dataframe, dropped_count = _drop_invalid_rssi_rows(dataframe)
    total_count = len(dataframe) + dropped_count
    print(
        f"[preprocess] Loại {dropped_count}/{total_count} mẫu RSSI không hợp lệ "
        f"(null hoặc ngoài [{config.RSSI_VALID_MIN}, {config.RSSI_VALID_MAX}]); "
        f"còn {len(dataframe)} mẫu hợp lệ."
    )

    if config.SPLIT_STRATEGY != "temporal":
        raise DataPreprocessingError(
            f"SPLIT_STRATEGY={config.SPLIT_STRATEGY!r} chưa được hỗ trợ. "
            "Hiện chỉ hỗ trợ 'temporal' (chia theo thời gian, chống rò rỉ)."
        )

    train_df, val_df, test_df = _split_by_time_per_cell(dataframe)

    scaler = _fit_and_save_scaler(train_df[RSSI_COLUMNS])
    train_df = _transform_rssi(train_df, scaler)
    val_df = _transform_rssi(val_df, scaler)
    test_df = _transform_rssi(test_df, scaler)

    return (
        _build_windows(train_df, RSSI_COLUMNS, "train"),
        _build_windows(val_df, RSSI_COLUMNS, "val"),
        _build_windows(test_df, RSSI_COLUMNS, "test"),
    )


def _enable_utf8_console() -> None:
    """Ép stdout/stderr sang UTF-8 để log tiếng Việt không vỡ trên console Windows.

    Console mặc định của Windows PowerShell dùng cp1252; in ký tự có dấu sẽ ném
    UnicodeEncodeError. reconfigure về utf-8 giúp log/traceback hiển thị đúng.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


if __name__ == "__main__":
    _enable_utf8_console()
    (X_train, y_train), (X_val, y_val), (X_test, y_test) = get_split_windows()
    print(f"Train X shape: {X_train.shape}, y shape: {y_train.shape}")
    print(f"Val   X shape: {X_val.shape}, y shape: {y_val.shape}")
    print(f"Test  X shape: {X_test.shape}, y shape: {y_test.shape}")
    print(f"Scaler saved to: {config.SCALER_PATH}")
