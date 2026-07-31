"""Local web test app for the trained RSSI Transformer model.

File này chạy độc lập với FastAPI server chính. Nó đọc dataset CSV giả lập MQTT,
đẩy từng dòng theo tốc độ cấu hình, tạo sliding window RSSI và hiển thị tọa độ
dự đoán của model Transformer trên bản đồ caro.
"""
from __future__ import annotations

import argparse
import math
import os
import signal
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


TEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.algorithms.transformer import config as transformer_config
from backend.algorithms.transformer.training.model_def import RSSITransformer


# ============================================================
# Editable defaults
# ============================================================

MAP_MAX_OX = 5
MAP_MAX_OY = 7
BLOCKED_CELLS = [1, 5, 6, 10, 11, 13, 15]
TRAJECTORY_CELLS = [32, 27, 22, 17, 12, 7, 8, 9, 14, 19, 24, 29, 34, 33,]
MAP_NAME = "ID 17"
TRAJECTORY_NAME = "test_case_18"
DATASET_PATH = PROJECT_ROOT / "test" / "tran_pdr_eskf" / "dataset" / "result" / "test_case_6.csv"
MESSAGE_RATE_HZ = 17.1
# Dải RSSI hợp lệ lấy từ config chung để khớp đúng quy tắc lọc dữ liệu lúc training.
RSSI_MIN = transformer_config.RSSI_VALID_MIN  # -99
RSSI_MAX = transformer_config.RSSI_VALID_MAX  # -1
MODEL_DIR = PROJECT_ROOT / "backend" / "algorithms" / "transformer" / "model" / "map_15" / "campaign_14"
HOST = "127.0.0.1"
PORT = 8036


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


@dataclass(frozen=True)
class AppConfig:
    """Cấu hình runtime cho test app."""

    max_ox: int = MAP_MAX_OX
    max_oy: int = MAP_MAX_OY
    blocked_cells: tuple[int, ...] = tuple(BLOCKED_CELLS)
    trajectory_cells: tuple[int, ...] = tuple(TRAJECTORY_CELLS)
    map_name: str = MAP_NAME
    trajectory_name: str = TRAJECTORY_NAME
    dataset_path: Path = DATASET_PATH
    message_rate_hz: float = MESSAGE_RATE_HZ
    rssi_min: int = RSSI_MIN
    rssi_max: int = RSSI_MAX
    model_dir: Path = MODEL_DIR
    host: str = HOST
    port: int = PORT

    @property
    def cell_count(self) -> int:
        return self.max_ox * self.max_oy

    @property
    def model_path(self) -> Path:
        return self.model_dir / "transformer_model.pt"

    @property
    def scaler_path(self) -> Path:
        return self.model_dir / "scaler.joblib"


def parse_index_list(value: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in value.replace(";", ",").split(",") if part.strip())


def validate_app_config(config: AppConfig) -> None:
    if config.max_ox <= 0 or config.max_oy <= 0:
        raise ValueError("max_ox and max_oy must be positive.")
    if config.message_rate_hz <= 0:
        raise ValueError("message_rate_hz must be greater than 0.")
    if config.rssi_min > config.rssi_max:
        raise ValueError("rssi_min must be <= rssi_max.")
    if not config.dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {config.dataset_path}")
    if not config.model_path.exists():
        raise FileNotFoundError(f"Model checkpoint not found: {config.model_path}")
    if not config.scaler_path.exists():
        raise FileNotFoundError(f"Scaler not found: {config.scaler_path}")

    invalid_blocked = [index for index in config.blocked_cells if index < 1 or index > config.cell_count]
    invalid_route = [index for index in config.trajectory_cells if index < 1 or index > config.cell_count]
    if invalid_blocked:
        raise ValueError(f"Blocked cell index out of range 1..{config.cell_count}: {invalid_blocked}")
    if invalid_route:
        raise ValueError(f"Trajectory cell index out of range 1..{config.cell_count}: {invalid_route}")


def index_to_cell_center(index: int, max_ox: int) -> Dict[str, float]:
    """Đổi cell index sang tâm ô theo hệ tọa độ Decartes mét."""
    zero_based = index - 1
    col = zero_based % max_ox
    row = zero_based // max_ox
    return {"x": col + 0.5, "y": row + 0.5}


def select_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


class TransformerPredictor:
    """Load scaler/model đã train và chạy inference cho từng window RSSI."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.device = select_device()
        self.scaler = joblib.load(config.scaler_path)
        self.model = RSSITransformer().to(self.device)
        state_dict = torch.load(config.model_path, map_location=self.device)
        self.model.load_state_dict(state_dict)
        self.model.eval()

    def extract_rssi_row(self, row: pd.Series) -> Optional[List[float]]:
        """Trích 8 kênh RSSI của 1 dòng; trả None nếu dòng KHÔNG hợp lệ.

        Khớp đúng quy tắc lọc lúc training: chỉ chấp nhận dòng có cả 8 kênh RSSI
        nằm trong dải hợp lệ [rssi_min, rssi_max] = [-99, -1]. Nếu bất kỳ kênh nào
        rỗng/NaN/không parse được/ngoài dải -> coi cả dòng là dữ liệu lỗi và BỎ QUA
        (không điền sentinel, không nạp vào model), giống hành vi training.
        """
        values: List[float] = []
        for column in RSSI_COLUMNS:
            try:
                raw = row[column]
                if pd.isna(raw) or str(raw).strip() == "":
                    return None
                value = float(raw)
            except (TypeError, ValueError):
                return None

            if math.isnan(value) or value < self.config.rssi_min or value > self.config.rssi_max:
                return None
            values.append(value)
        return values

    def predict_window(self, window: List[List[float]]) -> Dict[str, float]:
        """Scale window [35,8], chạy model và trả về tọa độ dự đoán."""
        frame = pd.DataFrame(window, columns=RSSI_COLUMNS)
        scaled = self.scaler.transform(frame)
        # Clamp về [0,1]: giá trị test nằm ngoài [min,max] mà scaler học từ train
        # sẽ bị map ra ngoài [0,1]; clip giúp input gần phân phối lúc train hơn.
        scaled = np.clip(scaled, 0.0, 1.0)
        tensor = torch.tensor(scaled, dtype=torch.float32, device=self.device).unsqueeze(0)

        with torch.no_grad():
            prediction = self.model(tensor).detach().cpu().numpy()[0]

        return {"x": float(prediction[0]), "y": float(prediction[1])}


@dataclass
class RuntimeState:
    running: bool = False
    finished: bool = False
    status: str = "idle"
    processed_rows: int = 0
    skipped_rows: int = 0
    total_rows: int = 0
    prediction_count: int = 0
    latest_prediction: Optional[Dict[str, Any]] = None
    predictions: List[Dict[str, Any]] = field(default_factory=list)
    started_at_unix: Optional[float] = None
    finished_at_unix: Optional[float] = None
    message: str = ""


class PredictionRuntime:
    """Quản lý worker đọc CSV theo tốc độ giả lập và cập nhật state cho frontend."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.predictor = TransformerPredictor(config)
        self.dataframe = self._load_dataset()
        self.lock = Lock()
        self.stop_event = Event()
        self.thread: Optional[Thread] = None
        self.state = RuntimeState(total_rows=len(self.dataframe))

    def _load_dataset(self) -> pd.DataFrame:
        dataframe = pd.read_csv(self.config.dataset_path)
        missing = [column for column in RSSI_COLUMNS if column not in dataframe.columns]
        if missing:
            raise ValueError(f"Dataset missing RSSI columns: {missing}")
        return dataframe

    def reset(self) -> Dict[str, Any]:
        self.stop_event.set()
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        with self.lock:
            self.state = RuntimeState(total_rows=len(self.dataframe), status="idle", message="Reset complete")
            self.thread = None
        return self.snapshot()

    def start(self) -> Dict[str, Any]:
        with self.lock:
            if self.state.running:
                return self.snapshot_unlocked()
            self.stop_event.clear()
            self.state = RuntimeState(
                running=True,
                finished=False,
                status="running",
                total_rows=len(self.dataframe),
                started_at_unix=time.time(),
                message="Streaming dataset",
            )

        self.thread = Thread(target=self._worker, name="transformer-test-stream", daemon=True)
        self.thread.start()
        return self.snapshot()

    def _worker(self) -> None:
        # Sử dụng deque để quản lý window một cách hiệu quả
        window_deque: deque = deque(maxlen=transformer_config.WINDOW_SIZE)
        step_size = 5  # STEP_SIZE từ quá trình training, dùng cho Downsampling
        counter = 0  # Đếm số mẫu đã nhét vào deque
        interval_seconds = 1.0 / self.config.message_rate_hz

        for row_number, (_, row) in enumerate(self.dataframe.iterrows(), start=1):
            if self.stop_event.is_set():
                break

            # Lọc dữ liệu lỗi: dòng có RSSI ngoài [-99,-1]/NaN bị BỎ QUA, không nạp model.
            sanitized = self.predictor.extract_rssi_row(row)
            if sanitized is None:
                with self.lock:
                    self.state.processed_rows = row_number
                    self.state.skipped_rows += 1
                    self.state.message = (
                        f"Bỏ qua dòng {row_number}: RSSI ngoài dải "
                        f"[{self.config.rssi_min}, {self.config.rssi_max}]"
                    )
                time.sleep(interval_seconds)
                continue

            window_deque.append(sanitized)
            counter += 1

            latest_prediction = None
            # COLD START: Chỉ dự đoán khi đủ 35 mẫu hợp lệ (chờ đủ ~1 giây đầu tiên)
            if len(window_deque) == transformer_config.WINDOW_SIZE:
                # DOWNSAMPLING: chỉ dự đoán mỗi step_size mẫu hợp lệ để giảm tải.
                if counter % step_size == 0:
                    predicted = self.predictor.predict_window(list(window_deque))
                    latest_prediction = {
                        "id": None,
                        "row": row_number,
                        "elapsed_s": round(row_number / self.config.message_rate_hz, 3),
                        "x": predicted["x"],
                        "y": predicted["y"],
                    }

            with self.lock:
                self.state.processed_rows = row_number
                if latest_prediction is not None:
                    latest_prediction["id"] = self.state.prediction_count + 1
                    self.state.prediction_count += 1
                    self.state.latest_prediction = latest_prediction
                    self.state.predictions.append(latest_prediction)
                    self.state.message = f"Predicting (downsampled, counter={counter})"
                else:
                    if len(window_deque) < transformer_config.WINDOW_SIZE:
                        self.state.message = f"Warming up window {len(window_deque)}/{transformer_config.WINDOW_SIZE}"
                    else:
                        self.state.message = f"Waiting for downsampling... ({counter % step_size}/{step_size})"

            time.sleep(interval_seconds)

        with self.lock:
            if self.stop_event.is_set():
                self.state.running = False
                self.state.finished = False
                self.state.status = "stopped"
                self.state.message = "Stopped"
            else:
                self.state.running = False
                self.state.finished = True
                self.state.status = "finished"
                self.state.finished_at_unix = time.time()
                self.state.message = "Finished"

    def snapshot_unlocked(self) -> Dict[str, Any]:
        return {
            "running": self.state.running,
            "finished": self.state.finished,
            "status": self.state.status,
            "processed_rows": self.state.processed_rows,
            "skipped_rows": self.state.skipped_rows,
            "total_rows": self.state.total_rows,
            "prediction_count": self.state.prediction_count,
            "latest_prediction": self.state.latest_prediction,
            "predictions": list(self.state.predictions),
            "started_at_unix": self.state.started_at_unix,
            "finished_at_unix": self.state.finished_at_unix,
            "message": self.state.message,
        }

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return self.snapshot_unlocked()


def build_frontend_config(config: AppConfig) -> Dict[str, Any]:
    return {
        "max_ox": config.max_ox,
        "max_oy": config.max_oy,
        "blocked_cells": list(config.blocked_cells),
        "trajectory_cells": list(config.trajectory_cells),
        "trajectory_centers": [
            index_to_cell_center(index, config.max_ox) for index in config.trajectory_cells
        ],
        "map_name": config.map_name,
        "trajectory_name": config.trajectory_name,
        "dataset_path": str(config.dataset_path),
        "message_rate_hz": config.message_rate_hz,
        "rssi_range": [config.rssi_min, config.rssi_max],
        "model_dir": str(config.model_dir),
        "window_size": transformer_config.WINDOW_SIZE,
        "input_dim": transformer_config.INPUT_DIM,
    }


def create_app(config: AppConfig) -> FastAPI:
    validate_app_config(config)
    runtime = PredictionRuntime(config)
    app = FastAPI(title="Transformer RSSI Model Test", version="1.0")
    app.mount("/static", StaticFiles(directory=TEST_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(TEST_DIR / "test_model.html")

    @app.get("/api/config")
    def get_config():
        return build_frontend_config(config)

    @app.post("/api/start")
    def start():
        try:
            return runtime.start()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/reset")
    def reset():
        return runtime.reset()

    @app.get("/api/state")
    def get_state():
        return runtime.snapshot()

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local web test for RSSI Transformer model.")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--max-ox", type=int, default=MAP_MAX_OX)
    parser.add_argument("--max-oy", type=int, default=MAP_MAX_OY)
    parser.add_argument("--blocked", default=",".join(str(index) for index in BLOCKED_CELLS))
    parser.add_argument("--trajectory", default=",".join(str(index) for index in TRAJECTORY_CELLS))
    parser.add_argument("--map-name", default=MAP_NAME)
    parser.add_argument("--trajectory-name", default=TRAJECTORY_NAME)
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--message-rate", type=float, default=MESSAGE_RATE_HZ)
    parser.add_argument("--rssi-min", type=int, default=RSSI_MIN)
    parser.add_argument("--rssi-max", type=int, default=RSSI_MAX)
    parser.add_argument("--model-dir", type=Path, default=MODEL_DIR)
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> AppConfig:
    return AppConfig(
        max_ox=args.max_ox,
        max_oy=args.max_oy,
        blocked_cells=parse_index_list(args.blocked),
        trajectory_cells=parse_index_list(args.trajectory),
        map_name=args.map_name,
        trajectory_name=args.trajectory_name,
        dataset_path=args.dataset.resolve(),
        message_rate_hz=args.message_rate,
        rssi_min=args.rssi_min,
        rssi_max=args.rssi_max,
        model_dir=args.model_dir.resolve(),
        host=args.host,
        port=args.port,
    )


def _enable_utf8_console() -> None:
    """Ép stdout/stderr sang UTF-8 để log có emoji/tiếng Việt không vỡ trên Windows."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def main() -> None:
    _enable_utf8_console()
    args = parse_args()
    app_config = config_from_args(args)
    app = create_app(app_config)
    
    # Graceful shutdown với Ctrl+C
    def signal_handler(signum, frame):
        print("\n⏹️  Tắt server...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print(f"\n🚀 Transformer test page: http://{app_config.host}:{app_config.port}")
    print(f"   Nhấn Ctrl+C để tắt\n")
    
    uvicorn.run(app, host=app_config.host, port=app_config.port, log_level="info")


if __name__ == "__main__":
    main()
