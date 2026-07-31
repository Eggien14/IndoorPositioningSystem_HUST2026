"""Local web test app for the PDR (Pedestrian Dead Reckoning) module.

File này chạy độc lập với FastAPI server chính. Nó đọc dataset CSV IMU đã thu, đẩy
từng dòng theo tốc độ cấu hình, chạy PDRModel để phát hiện bước, và cộng dồn vị trí
TỪ MỘT Ô KHỞI ĐẦU để vẽ quỹ đạo dead-reckoning thuần PDR trên bản đồ caro.

LƯU Ý: việc cộng dồn vị trí ở đây CHỈ để trực quan/đánh giá drift của PDR. Trong hệ
thống thật, ESKF mới là khối cộng dồn (PDR chỉ cung cấp displacement + uncertainty).

Logic vẽ bản đồ / index ô / quỹ đạo tham khảo y hệt test/transformer/test_model.py,
chỉ thay thuật toán Transformer bằng PDR.
"""
from __future__ import annotations

import argparse
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, Dict, List, Optional

import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


TEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.algorithms.pdr import config as pdr_config
from backend.algorithms.pdr.pdr_model import PDRModel


# ============================================================
# Editable defaults
# ============================================================

MAP_MAX_OX = 5
MAP_MAX_OY = 10
BLOCKED_CELLS = [48, 49, 50]
TRAJECTORY_CELLS = [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 47, 43, 44, 45, 40, 35, 30, 25, 20, 15, 10, 5, 4, 3, 2]
MAP_NAME = "ID 17"
TRAJECTORY_NAME = "test_case_D8"
DATASET_PATH = TEST_DIR / "dataset" / "result" / "test_case_D8_1_1.csv"
MESSAGE_RATE_HZ = 17.1

# Ô khởi đầu của quỹ đạo: PDR thuần cần điểm xuất phát để cộng dồn vị trí.
START_CELL = 1

# Tham số PDR (có thể override qua CLI).
# Map 17 (D8): Ox(5m)=North, Oy(10m)=West. Theo quy ước yaw_map=0 ⇒ đi +Oy(West),
# nên góc lệch BẢN ĐỒ = -90 (chính xác).
# offset_angle_bno: HIỆU CHỈNH từ dữ liệu — 15 bước đầu (đi thẳng +Oy) có yaw_raw
# ổn định ~164.7°, nên tổng offset = 164.7 ⇒ offset_bno = 164.7-(-90) ≈ -105°.
# (BNO lệch ~-105°, KHÔNG phải bội số 90° — gồm cả lệch gắn + lệch từ trường.)
OFFSET_ANGLE = -90.0        # góc lệch bản đồ (DB) — chính xác
OFFSET_ANGLE_BNO = -105.0   # bù lỗi hướng BNO, hiệu chỉnh từ đoạn đi thẳng +Oy
STEP_LENGTH_MODEL = pdr_config.STEP_LENGTH_MODEL          # "fixed" | "weinberg" | "kim"
LOWPASS_CUTOFF_HZ = pdr_config.LOWPASS_CUTOFF_HZ
USE_ACC_MAGNITUDE = pdr_config.USE_ACC_MAGNITUDE

HOST = "127.0.0.1"
PORT = 8038

IMU_COLUMNS = ["acc_x", "acc_y", "acc_z", "yaw"]


@dataclass(frozen=True)
class AppConfig:
    """Cấu hình runtime cho PDR test app."""

    max_ox: int = MAP_MAX_OX
    max_oy: int = MAP_MAX_OY
    blocked_cells: tuple[int, ...] = tuple(BLOCKED_CELLS)
    trajectory_cells: tuple[int, ...] = tuple(TRAJECTORY_CELLS)
    map_name: str = MAP_NAME
    trajectory_name: str = TRAJECTORY_NAME
    dataset_path: Path = DATASET_PATH
    message_rate_hz: float = MESSAGE_RATE_HZ
    start_cell: int = START_CELL
    offset_angle: float = OFFSET_ANGLE
    offset_angle_bno: float = OFFSET_ANGLE_BNO
    step_length_model: str = STEP_LENGTH_MODEL
    lowpass_cutoff_hz: float = LOWPASS_CUTOFF_HZ
    use_acc_magnitude: bool = USE_ACC_MAGNITUDE
    host: str = HOST
    port: int = PORT

    @property
    def cell_count(self) -> int:
        return self.max_ox * self.max_oy


def parse_index_list(value: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in value.replace(";", ",").split(",") if part.strip())


def index_to_cell_center(index: int, max_ox: int) -> Dict[str, float]:
    """Đổi cell index sang tâm ô theo hệ tọa độ Decartes mét (Ox phải, Oy lên)."""
    zero_based = index - 1
    col = zero_based % max_ox
    row = zero_based // max_ox
    return {"x": col + 0.5, "y": row + 0.5}


def validate_app_config(config: AppConfig) -> None:
    if config.max_ox <= 0 or config.max_oy <= 0:
        raise ValueError("max_ox and max_oy must be positive.")
    if config.message_rate_hz <= 0:
        raise ValueError("message_rate_hz must be greater than 0.")
    if not config.dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {config.dataset_path}")
    if config.start_cell < 1 or config.start_cell > config.cell_count:
        raise ValueError(f"start_cell out of range 1..{config.cell_count}: {config.start_cell}")

    invalid_blocked = [i for i in config.blocked_cells if i < 1 or i > config.cell_count]
    invalid_route = [i for i in config.trajectory_cells if i < 1 or i > config.cell_count]
    if invalid_blocked:
        raise ValueError(f"Blocked cell index out of range 1..{config.cell_count}: {invalid_blocked}")
    if invalid_route:
        raise ValueError(f"Trajectory cell index out of range 1..{config.cell_count}: {invalid_route}")


@dataclass
class RuntimeState:
    running: bool = False
    finished: bool = False
    status: str = "idle"
    processed_rows: int = 0
    total_rows: int = 0
    step_count: int = 0
    latest_prediction: Optional[Dict[str, Any]] = None
    predictions: List[Dict[str, Any]] = field(default_factory=list)
    started_at_unix: Optional[float] = None
    finished_at_unix: Optional[float] = None
    message: str = ""


class PDRRuntime:
    """Đọc CSV IMU theo tốc độ giả lập, chạy PDR và cộng dồn vị trí từ ô khởi đầu."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.dataframe = self._load_dataset()
        self.start_center = index_to_cell_center(config.start_cell, config.max_ox)
        self.lock = Lock()
        self.stop_event = Event()
        self.thread: Optional[Thread] = None
        self.state = RuntimeState(total_rows=len(self.dataframe))

    def _load_dataset(self) -> pd.DataFrame:
        dataframe = pd.read_csv(self.config.dataset_path)
        missing = [c for c in IMU_COLUMNS if c not in dataframe.columns]
        if missing:
            raise ValueError(f"Dataset missing IMU columns: {missing}")
        return dataframe

    def _new_pdr(self) -> PDRModel:
        return PDRModel(
            offset_angle=self.config.offset_angle,
            offset_angle_bno=self.config.offset_angle_bno,
            step_length_model=self.config.step_length_model,
            lowpass_cutoff_hz=self.config.lowpass_cutoff_hz,
            use_acc_magnitude=self.config.use_acc_magnitude,
        )

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
            start_point = {
                "id": 0,
                "row": 0,
                "step_index": 0,
                "x": self.start_center["x"],
                "y": self.start_center["y"],
                "heading": None,
                "step_length": None,
            }
            self.state = RuntimeState(
                running=True,
                status="running",
                total_rows=len(self.dataframe),
                started_at_unix=time.time(),
                latest_prediction=start_point,
                predictions=[start_point],   # quỹ đạo bắt đầu tại ô khởi đầu
                message=f"Streaming tu o {self.config.start_cell}",
            )

        self.thread = Thread(target=self._worker, name="pdr-test-stream", daemon=True)
        self.thread.start()
        return self.snapshot()

    def _worker(self) -> None:
        pdr = self._new_pdr()
        pos_x = self.start_center["x"]
        pos_y = self.start_center["y"]
        interval_seconds = 1.0 / self.config.message_rate_hz
        timestamp_step_ms = 1000.0 / self.config.message_rate_hz

        for row_number, (_, row) in enumerate(self.dataframe.iterrows(), start=1):
            if self.stop_event.is_set():
                break

            timestamp_ms = row_number * timestamp_step_ms
            event = pdr.process_imu_stream(
                acc_z=row["acc_z"],
                yaw=row["yaw"],
                timestamp=timestamp_ms,
                acc_x=row.get("acc_x"),
                acc_y=row.get("acc_y"),
            )

            new_point = None
            if event is not None:
                pos_x += event.delta_x
                pos_y += event.delta_y
                new_point = {
                    "id": event.step_index,
                    "row": row_number,
                    "step_index": event.step_index,
                    "x": pos_x,
                    "y": pos_y,
                    "heading": round(event.heading_deg, 1),
                    "step_length": round(event.step_length, 3),
                }

            with self.lock:
                self.state.processed_rows = row_number
                if new_point is not None:
                    self.state.step_count = event.step_index
                    self.state.latest_prediction = new_point
                    self.state.predictions.append(new_point)
                    self.state.message = (
                        f"Buoc {event.step_index}: L={event.step_length:.2f}m "
                        f"heading={event.heading_deg:.0f}"
                    )

            time.sleep(interval_seconds)

        with self.lock:
            if self.stop_event.is_set():
                self.state.running = False
                self.state.status = "stopped"
                self.state.message = "Stopped"
            else:
                self.state.running = False
                self.state.finished = True
                self.state.status = "finished"
                self.state.finished_at_unix = time.time()
                self.state.message = f"Finished - {self.state.step_count} buoc"

    def snapshot_unlocked(self) -> Dict[str, Any]:
        return {
            "running": self.state.running,
            "finished": self.state.finished,
            "status": self.state.status,
            "processed_rows": self.state.processed_rows,
            "total_rows": self.state.total_rows,
            "step_count": self.state.step_count,
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
            index_to_cell_center(i, config.max_ox) for i in config.trajectory_cells
        ],
        "map_name": config.map_name,
        "trajectory_name": config.trajectory_name,
        "dataset_path": str(config.dataset_path),
        "message_rate_hz": config.message_rate_hz,
        "start_cell": config.start_cell,
        "start_center": index_to_cell_center(config.start_cell, config.max_ox),
        "offset_angle": config.offset_angle,
        "offset_angle_bno": config.offset_angle_bno,
        "step_length_model": config.step_length_model,
        "lowpass_cutoff_hz": config.lowpass_cutoff_hz,
    }


def create_app(config: AppConfig) -> FastAPI:
    validate_app_config(config)
    runtime = PDRRuntime(config)
    app = FastAPI(title="PDR Dead Reckoning Test", version="1.0")
    app.mount("/static", StaticFiles(directory=TEST_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(TEST_DIR / "test_pdr.html")

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
    parser = argparse.ArgumentParser(description="Run local web test for the PDR module.")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--max-ox", type=int, default=MAP_MAX_OX)
    parser.add_argument("--max-oy", type=int, default=MAP_MAX_OY)
    parser.add_argument("--blocked", default=",".join(str(i) for i in BLOCKED_CELLS))
    parser.add_argument("--trajectory", default=",".join(str(i) for i in TRAJECTORY_CELLS))
    parser.add_argument("--map-name", default=MAP_NAME)
    parser.add_argument("--trajectory-name", default=TRAJECTORY_NAME)
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--message-rate", type=float, default=MESSAGE_RATE_HZ)
    parser.add_argument("--start-cell", type=int, default=START_CELL)
    parser.add_argument("--offset-angle", type=float, default=OFFSET_ANGLE)
    parser.add_argument("--offset-angle-bno", type=float, default=OFFSET_ANGLE_BNO)
    parser.add_argument("--step-model", default=STEP_LENGTH_MODEL, choices=["fixed", "weinberg", "kim"])
    parser.add_argument("--lowpass-cutoff", type=float, default=LOWPASS_CUTOFF_HZ)
    parser.add_argument("--use-magnitude", action="store_true", default=USE_ACC_MAGNITUDE)
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
        start_cell=args.start_cell,
        offset_angle=args.offset_angle,
        offset_angle_bno=args.offset_angle_bno,
        step_length_model=args.step_model,
        lowpass_cutoff_hz=args.lowpass_cutoff,
        use_acc_magnitude=args.use_magnitude,
        host=args.host,
        port=args.port,
    )


def _enable_utf8_console() -> None:
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

    def signal_handler(signum, frame):
        print("\nTat server...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    print(f"\nPDR test page: http://{app_config.host}:{app_config.port}")
    print(f"  Dataset: {app_config.dataset_path.name} | start_cell={app_config.start_cell} | "
          f"model={app_config.step_length_model}")
    print("  Nhan Ctrl+C de tat\n")

    uvicorn.run(app, host=app_config.host, port=app_config.port, log_level="info")


if __name__ == "__main__":
    main()
