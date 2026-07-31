"""Simple trajectory simulator for testing trajectory-based positioning.

File này là phiên bản đơn giản hơn của test_model.py:
- Không sử dụng model Transformer để dự đoán
- Sinh điểm dự báo trực tiếp từ quỹ đạo đã khai báo
- Thêm sai số theo phân phối chuẩn (Gaussian noise: 0-0.5m)
- Giữ nguyên cấu trúc API để tái sử dụng frontend
"""
from __future__ import annotations

import argparse
import math
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, Dict, List, Optional

import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


TEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ============================================================
# Editable defaults
# ============================================================

MAP_MAX_OX = 5
MAP_MAX_OY = 10
BLOCKED_CELLS = [48, 49, 50]
TRAJECTORY_CELLS = [1,6,11,16,21,26,31,36,41,46,47,43,44,45,40,35,30,25,20,15,10,5,4,3,2]
MAP_NAME = "ID 17"
TRAJECTORY_NAME = "test_case_18"
NUM_PREDICTIONS = 270  # Số điểm dự báo mặc định
NOISE_STD_DEV = 0.35  # Độ lệch chuẩn của sai số (meter), tức 0-0.5m khoảng ±2 sigma
MESSAGE_RATE_HZ = 7.0  # Tốc độ phát hành dự báo (7Hz)
HOST = "127.0.0.1"
PORT = 8036


@dataclass(frozen=True)
class AppConfig:
    """Cấu hình runtime cho test app."""

    max_ox: int = MAP_MAX_OX
    max_oy: int = MAP_MAX_OY
    blocked_cells: tuple[int, ...] = tuple(BLOCKED_CELLS)
    trajectory_cells: tuple[int, ...] = tuple(TRAJECTORY_CELLS)
    map_name: str = MAP_NAME
    trajectory_name: str = TRAJECTORY_NAME
    num_predictions: int = NUM_PREDICTIONS
    noise_std_dev: float = NOISE_STD_DEV
    message_rate_hz: float = MESSAGE_RATE_HZ
    host: str = HOST
    port: int = PORT

    @property
    def cell_count(self) -> int:
        return self.max_ox * self.max_oy


def parse_index_list(value: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in value.replace(";", ",").split(",") if part.strip())


def validate_app_config(config: AppConfig) -> None:
    if config.max_ox <= 0 or config.max_oy <= 0:
        raise ValueError("max_ox and max_oy must be positive.")
    if config.message_rate_hz <= 0:
        raise ValueError("message_rate_hz must be greater than 0.")
    if config.num_predictions <= 0:
        raise ValueError("num_predictions must be greater than 0.")

    invalid_blocked = [index for index in config.blocked_cells if index < 1 or index > config.cell_count]
    invalid_route = [index for index in config.trajectory_cells if index < 1 or index > config.cell_count]
    if invalid_blocked:
        raise ValueError(f"Blocked cell index out of range 1..{config.cell_count}: {invalid_blocked}")
    if invalid_route:
        raise ValueError(f"Trajectory cell index out of range 1..{config.cell_count}: {invalid_route}")


def index_to_cell_center(index: int, max_ox: int) -> Dict[str, float]:
    """Đổi cell index sang tâm ô theo hệ tọa độ Descartes."""
    zero_based = index - 1
    col = zero_based % max_ox
    row = zero_based // max_ox
    return {"x": col + 0.5, "y": row + 0.5}


def point_in_blocked_cell(
    x: float,
    y: float,
    max_ox: int,
    max_oy: int,
    blocked_cells: set,
) -> bool:
    """Kiểm tra xem điểm (x, y) có nằm trong blocked cell không."""
    col = int(x)
    row = int(y)
    # Kiểm tra ranh giới
    if col < 0 or col >= max_ox or row < 0 or row >= max_oy:
        return True  # Ngoài biên cũng coi là blocked
    # Tính cell index (1-indexed)
    cell_index = row * max_ox + col + 1
    return cell_index in blocked_cells


def interpolate_trajectory(
    trajectory_cells: tuple[int, ...],
    max_ox: int,
    max_oy: int,
    num_points: int,
    noise_std_dev: float,
    blocked_cells: tuple[int, ...],
) -> List[Dict[str, float]]:
    """
    Sinh điểm dự báo bằng cách nội suy (interpolate) dọc theo quỹ đạo.
    Loại bỏ các điểm nằm trong blocked cells.
    
    Args:
        trajectory_cells: Danh sách các cell index theo thứ tự quỹ đạo
        max_ox: Số cột lưới
        max_oy: Số hàng lưới
        num_points: Số điểm dự báo cần sinh
        noise_std_dev: Độ lệch chuẩn của sai số Gaussian (meter)
        blocked_cells: Tập hợp các cell index bị chặn
    
    Returns:
        Danh sách tọa độ dự báo với sai số (không chứa điểm trong blocked cells)
    """
    if len(trajectory_cells) < 2:
        raise ValueError("Trajectory must have at least 2 cells")

    blocked_set = set(blocked_cells)

    # Lấy tâm của các cell trên quỹ đạo
    waypoints = [index_to_cell_center(cell, max_ox) for cell in trajectory_cells]

    # Tính độ dài từng đoạn
    segment_lengths = []
    total_length = 0.0
    for i in range(len(waypoints) - 1):
        dx = waypoints[i + 1]["x"] - waypoints[i]["x"]
        dy = waypoints[i + 1]["y"] - waypoints[i]["y"]
        dist = math.sqrt(dx**2 + dy**2)
        segment_lengths.append(dist)
        total_length += dist

    # Sinh các tham số s theo khoảng cách từ 0 đến total_length
    s_values = np.linspace(0, total_length, num_points)

    predictions = []
    for s in s_values:
        # Tìm đoạn hiện tại
        cumulative = 0.0
        for i in range(len(segment_lengths)):
            if cumulative + segment_lengths[i] >= s:
                # Nội suy trong đoạn i
                ratio = (s - cumulative) / segment_lengths[i] if segment_lengths[i] > 0 else 0
                p1 = waypoints[i]
                p2 = waypoints[i + 1]
                x = p1["x"] + ratio * (p2["x"] - p1["x"])
                y = p1["y"] + ratio * (p2["y"] - p1["y"])
                break
            cumulative += segment_lengths[i]
        else:
            # Điểm cuối
            x = waypoints[-1]["x"]
            y = waypoints[-1]["y"]

        # Thêm Gaussian noise
        noise_x = np.random.normal(0, noise_std_dev)
        noise_y = np.random.normal(0, noise_std_dev)
        
        final_x = x + noise_x
        final_y = y + noise_y

        # Kiểm tra điểm không nằm trong blocked cell
        if not point_in_blocked_cell(final_x, final_y, max_ox, max_oy, blocked_set):
            predictions.append({
                "x": float(final_x),
                "y": float(final_y),
            })

    return predictions


@dataclass
class RuntimeState:
    running: bool = False
    finished: bool = False
    status: str = "idle"
    processed_count: int = 0
    total_count: int = 0
    prediction_count: int = 0
    latest_prediction: Optional[Dict[str, Any]] = None
    predictions: List[Dict[str, Any]] = field(default_factory=list)
    started_at_unix: Optional[float] = None
    finished_at_unix: Optional[float] = None
    message: str = ""


class TrajectorySimulator:
    """Quản lý phát hành predictions từ quỹ đạo theo tốc độ giả lập."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.predictions = interpolate_trajectory(
            config.trajectory_cells,
            config.max_ox,
            config.max_oy,
            config.num_predictions,
            config.noise_std_dev,
            config.blocked_cells,
        )
        self.lock = Lock()
        self.stop_event = Event()
        self.thread: Optional[Thread] = None
        self.state = RuntimeState(total_count=len(self.predictions))

    def reset(self) -> Dict[str, Any]:
        self.stop_event.set()
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        with self.lock:
            self.state = RuntimeState(
                total_count=len(self.predictions),
                status="idle",
                message="Reset complete"
            )
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
                total_count=len(self.predictions),
                started_at_unix=time.time(),
                message="Streaming predictions from trajectory",
            )

        self.thread = Thread(target=self._worker, name="trajectory-simulator", daemon=True)
        self.thread.start()
        return self.snapshot()

    def _worker(self) -> None:
        interval_seconds = 1.0 / self.config.message_rate_hz

        for idx, prediction in enumerate(self.predictions):
            if self.stop_event.is_set():
                break

            latest_prediction = {
                "id": idx + 1,
                "row": idx + 1,
                "elapsed_s": round((idx + 1) / self.config.message_rate_hz, 3),
                "x": prediction["x"],
                "y": prediction["y"],
            }

            with self.lock:
                self.state.processed_count = idx + 1
                self.state.prediction_count = idx + 1
                self.state.latest_prediction = latest_prediction
                self.state.predictions.append(latest_prediction)
                self.state.message = f"Predicting point {idx + 1}/{len(self.predictions)}"

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
            "processed_rows": self.state.processed_count,
            "total_rows": self.state.total_count,
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
        "num_predictions": config.num_predictions,
        "noise_std_dev": config.noise_std_dev,
        "message_rate_hz": config.message_rate_hz,
    }


def create_app(config: AppConfig) -> FastAPI:
    validate_app_config(config)
    simulator = TrajectorySimulator(config)
    app = FastAPI(title="Trajectory Simulator", version="1.0")
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
            return simulator.start()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/reset")
    def reset():
        return simulator.reset()

    @app.get("/api/state")
    def get_state():
        return simulator.snapshot()

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run trajectory simulator for testing.")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--max-ox", type=int, default=MAP_MAX_OX)
    parser.add_argument("--max-oy", type=int, default=MAP_MAX_OY)
    parser.add_argument("--blocked", default=",".join(str(index) for index in BLOCKED_CELLS))
    parser.add_argument("--trajectory", default=",".join(str(index) for index in TRAJECTORY_CELLS))
    parser.add_argument("--map-name", default=MAP_NAME)
    parser.add_argument("--trajectory-name", default=TRAJECTORY_NAME)
    parser.add_argument("--num-predictions", type=int, default=NUM_PREDICTIONS)
    parser.add_argument("--noise-std", type=float, default=NOISE_STD_DEV)
    parser.add_argument("--message-rate", type=float, default=MESSAGE_RATE_HZ)
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> AppConfig:
    return AppConfig(
        max_ox=args.max_ox,
        max_oy=args.max_oy,
        blocked_cells=parse_index_list(args.blocked),
        trajectory_cells=parse_index_list(args.trajectory),
        map_name=args.map_name,
        trajectory_name=args.trajectory_name,
        num_predictions=args.num_predictions,
        noise_std_dev=args.noise_std,
        message_rate_hz=args.message_rate,
        host=args.host,
        port=args.port,
    )


def main() -> None:
    args = parse_args()
    app_config = config_from_args(args)
    app = create_app(app_config)

    # Graceful shutdown với Ctrl+C
    def signal_handler(signum, frame):
        print("\n⏹️  Tắt server...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    print(f"\n🚀 Trajectory simulator: http://{app_config.host}:{app_config.port}")
    print(f"   Nhấn Ctrl+C để tắt\n")

    uvicorn.run(app, host=app_config.host, port=app_config.port, log_level="info")


if __name__ == "__main__":
    main()
