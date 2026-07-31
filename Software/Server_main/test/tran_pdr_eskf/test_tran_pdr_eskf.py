"""Local web test for the FULL Algorithm 3 pipeline (Transformer + PDR + ESKF).

Phát lại một dataset CSV có CẢ RSSI lẫn IMU, chạy đồng thời:
- Transformer  -> observation (x,y)        [chấm xanh lá, nhiễu]
- PDR thuần    -> quỹ đạo dead-reckoning    [đường cam, trôi]
- ESKF fused   -> vị trí cuối cùng          [đường xanh dương, kết quả chính]

So với quỹ đạo tham chiếu (mũi tên xám) để thấy ESKF vừa khử drift PDR vừa ghìm
nhảy NLOS của Transformer. Logic vẽ bản đồ/index ô y hệt test/transformer & test/pdr.
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

from backend.algorithm_3 import Algorithm3, RSSI_COLUMNS
from backend.algorithms.pdr.pdr_model import PDRModel


# ============================================================
# Editable defaults  (map 17 / D8)
# ============================================================

# MAP_MAX_OX = 5
# MAP_MAX_OY = 10
# BLOCKED_CELLS = [48, 49, 50]
# TRAJECTORY_CELLS = [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 47, 43, 44, 45, 40, 35, 30, 25, 20, 15, 10, 5, 4, 3, 2]
# MAP_NAME = "ID 17"
# TRAJECTORY_NAME = "test_case_D8 (Transformer+PDR+ESKF)"
# DATASET_PATH = PROJECT_ROOT / "test" / "tran_pdr_eskf" / "dataset" / "result" / "test_case_D8_1_1.csv"
# MODEL_DIR = PROJECT_ROOT / "backend" / "algorithms" / "transformer" / "model" / "map_17" / "campaign_18"
# MESSAGE_RATE_HZ = 17.1
# START_CELL = 1
MAP_MAX_OX = 5
MAP_MAX_OY = 7
BLOCKED_CELLS = [1, 5, 6, 10, 11, 13, 15]
TRAJECTORY_CELLS = [32, 27, 22, 17, 12, 7, 8, 9, 14, 19, 24, 29, 34, 33,]
MAP_NAME = "ID 17"
TRAJECTORY_NAME = "test_case_D8 (Transformer+PDR+ESKF)"
DATASET_PATH = PROJECT_ROOT / "test" / "tran_pdr_eskf" / "dataset" / "result" / "test_case_6.csv"
MODEL_DIR = PROJECT_ROOT / "backend" / "algorithms" / "transformer" / "model" / "map_15" / "campaign_14"
MESSAGE_RATE_HZ = 34.994
START_CELL = 32

# Tham số PDR (đã calib cho map 17/D8 — xem backend/algorithms/pdr).
OFFSET_ANGLE = -75
OFFSET_ANGLE_BNO = -105.0
STEP_LENGTH_MODEL = "weinberg"

HOST = "127.0.0.1"
PORT = 8041

IMU_COLUMNS = ["acc_x", "acc_y", "acc_z", "yaw"]


@dataclass(frozen=True)
class AppConfig:
    max_ox: int = MAP_MAX_OX
    max_oy: int = MAP_MAX_OY
    blocked_cells: tuple[int, ...] = tuple(BLOCKED_CELLS)
    trajectory_cells: tuple[int, ...] = tuple(TRAJECTORY_CELLS)
    map_name: str = MAP_NAME
    trajectory_name: str = TRAJECTORY_NAME
    dataset_path: Path = DATASET_PATH
    model_dir: Path = MODEL_DIR
    message_rate_hz: float = MESSAGE_RATE_HZ
    start_cell: int = START_CELL
    offset_angle: float = OFFSET_ANGLE
    offset_angle_bno: float = OFFSET_ANGLE_BNO
    step_length_model: str = STEP_LENGTH_MODEL
    host: str = HOST
    port: int = PORT

    @property
    def cell_count(self) -> int:
        return self.max_ox * self.max_oy


def parse_index_list(value: str) -> tuple[int, ...]:
    return tuple(int(p.strip()) for p in value.replace(";", ",").split(",") if p.strip())


def index_to_cell_center(index: int, max_ox: int) -> Dict[str, float]:
    z = index - 1
    return {"x": z % max_ox + 0.5, "y": z // max_ox + 0.5}


def validate_app_config(config: AppConfig) -> None:
    if config.max_ox <= 0 or config.max_oy <= 0:
        raise ValueError("max_ox and max_oy must be positive.")
    if config.message_rate_hz <= 0:
        raise ValueError("message_rate_hz must be greater than 0.")
    if not config.dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {config.dataset_path}")
    if not (config.model_dir / "transformer_model.pt").exists():
        raise FileNotFoundError(f"Model not found in: {config.model_dir}")
    if config.start_cell < 1 or config.start_cell > config.cell_count:
        raise ValueError(f"start_cell out of range 1..{config.cell_count}: {config.start_cell}")


@dataclass
class RuntimeState:
    running: bool = False
    finished: bool = False
    status: str = "idle"
    processed_rows: int = 0
    total_rows: int = 0
    step_count: int = 0
    update_count: int = 0
    rejected_count: int = 0
    fused: List[Dict[str, Any]] = field(default_factory=list)
    pdr_only: List[Dict[str, Any]] = field(default_factory=list)
    obs: List[Dict[str, Any]] = field(default_factory=list)
    latest_fused: Optional[Dict[str, Any]] = None
    message: str = ""


class FusionRuntime:
    """Phát lại CSV, chạy Algorithm3 (fused) + PDR thuần + thu observation Transformer."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.dataframe = self._load_dataset()
        self.start_center = index_to_cell_center(config.start_cell, config.max_ox)
        self.lock = Lock()
        self.stop_event = Event()
        self.thread: Optional[Thread] = None
        self.state = RuntimeState(total_rows=len(self.dataframe))

    def _load_dataset(self) -> pd.DataFrame:
        df = pd.read_csv(self.config.dataset_path)
        missing = [c for c in (IMU_COLUMNS + RSSI_COLUMNS) if c not in df.columns]
        if missing:
            raise ValueError(f"Dataset missing columns: {missing}")
        return df

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
            start_pt = {"x": self.start_center["x"], "y": self.start_center["y"]}
            self.state = RuntimeState(
                running=True,
                status="running",
                total_rows=len(self.dataframe),
                fused=[dict(start_pt)],
                pdr_only=[dict(start_pt)],
                latest_fused=dict(start_pt),
                message=f"Streaming tu o {self.config.start_cell}",
            )
        self.thread = Thread(target=self._worker, name="fusion-test-stream", daemon=True)
        self.thread.start()
        return self.snapshot()

    def _worker(self) -> None:
        cfg = self.config
        algo = Algorithm3(
            model_dir=cfg.model_dir,
            start_x=self.start_center["x"],
            start_y=self.start_center["y"],
            offset_angle=cfg.offset_angle,
            offset_angle_bno=cfg.offset_angle_bno,
            step_length_model=cfg.step_length_model,
        )
        # PDR thuần (tham chiếu so sánh) — cùng tham số, tự cộng dồn từ ô khởi đầu.
        pdr_only = PDRModel(
            offset_angle=cfg.offset_angle,
            offset_angle_bno=cfg.offset_angle_bno,
            step_length_model=cfg.step_length_model,
        )
        px, py = self.start_center["x"], self.start_center["y"]
        interval = 1.0 / cfg.message_rate_hz
        dt_ms = 1000.0 / cfg.message_rate_hz

        for row_number, (_, row) in enumerate(self.dataframe.iterrows(), start=1):
            if self.stop_event.is_set():
                break
            t = row_number * dt_ms

            # --- Fused (Algorithm3): predict bằng PDR, update bằng Transformer ---
            ev = algo.process_imu(row["acc_z"], row["yaw"], t, row.get("acc_x"), row.get("acc_y"))
            res = algo.process_rssi([row[c] for c in RSSI_COLUMNS], t)

            # --- PDR thuần để so sánh ---
            ev2 = pdr_only.process_imu_stream(row["acc_z"], row["yaw"], t, row.get("acc_x"), row.get("acc_y"))
            if ev2 is not None:
                px += ev2.delta_x
                py += ev2.delta_y

            fused_changed = ev is not None or (res is not None and res[2])

            with self.lock:
                self.state.processed_rows = row_number
                if ev2 is not None:
                    self.state.pdr_only.append({"x": px, "y": py})
                if res is not None:
                    z_x, z_y, accepted = res
                    self.state.obs.append({"x": z_x, "y": z_y, "accepted": bool(accepted)})
                if fused_changed:
                    s = algo.get_state()
                    fp = {"x": s.fused_x, "y": s.fused_y}
                    self.state.fused.append(fp)
                    self.state.latest_fused = fp
                    self.state.step_count = s.step_count
                    self.state.update_count = s.update_count
                    self.state.rejected_count = s.rejected_count
                    self.state.message = (
                        f"steps={s.step_count} updates={s.update_count} "
                        f"rejected={s.rejected_count} std={s.pos_std:.2f}m"
                    )
            time.sleep(interval)

        with self.lock:
            self.state.running = False
            if self.stop_event.is_set():
                self.state.status = "stopped"; self.state.message = "Stopped"
            else:
                self.state.finished = True; self.state.status = "finished"
                self.state.message = f"Finished - {self.state.step_count} buoc, {self.state.update_count} updates"

    def snapshot_unlocked(self) -> Dict[str, Any]:
        return {
            "running": self.state.running,
            "finished": self.state.finished,
            "status": self.state.status,
            "processed_rows": self.state.processed_rows,
            "total_rows": self.state.total_rows,
            "step_count": self.state.step_count,
            "update_count": self.state.update_count,
            "rejected_count": self.state.rejected_count,
            "fused": list(self.state.fused),
            "pdr_only": list(self.state.pdr_only),
            "obs": list(self.state.obs),
            "latest_fused": self.state.latest_fused,
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
        "map_name": config.map_name,
        "trajectory_name": config.trajectory_name,
        "dataset_path": str(config.dataset_path),
        "message_rate_hz": config.message_rate_hz,
        "start_cell": config.start_cell,
        "start_center": index_to_cell_center(config.start_cell, config.max_ox),
        "offset_angle": config.offset_angle,
        "offset_angle_bno": config.offset_angle_bno,
        "step_length_model": config.step_length_model,
    }


def create_app(config: AppConfig) -> FastAPI:
    validate_app_config(config)
    runtime = FusionRuntime(config)
    app = FastAPI(title="Algorithm 3 Fusion Test (Transformer+PDR+ESKF)", version="1.0")
    app.mount("/static", StaticFiles(directory=TEST_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(TEST_DIR / "test_tran_pdr_eskf.html")

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
    parser = argparse.ArgumentParser(description="Run local web test for full Algorithm 3 fusion.")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--model-dir", type=Path, default=MODEL_DIR)
    parser.add_argument("--message-rate", type=float, default=MESSAGE_RATE_HZ)
    parser.add_argument("--start-cell", type=int, default=START_CELL)
    parser.add_argument("--offset-angle", type=float, default=OFFSET_ANGLE)
    parser.add_argument("--offset-angle-bno", type=float, default=OFFSET_ANGLE_BNO)
    parser.add_argument("--step-model", default=STEP_LENGTH_MODEL, choices=["fixed", "weinberg", "kim"])
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> AppConfig:
    return AppConfig(
        dataset_path=args.dataset.resolve(),
        model_dir=args.model_dir.resolve(),
        message_rate_hz=args.message_rate,
        start_cell=args.start_cell,
        offset_angle=args.offset_angle,
        offset_angle_bno=args.offset_angle_bno,
        step_length_model=args.step_model,
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
    print(f"\nAlgorithm 3 fusion test: http://{app_config.host}:{app_config.port}")
    print(f"  Dataset: {app_config.dataset_path.name} | model: {app_config.model_dir.name}")
    print("  Nhan Ctrl+C de tat\n")
    uvicorn.run(app, host=app_config.host, port=app_config.port, log_level="info")


if __name__ == "__main__":
    main()
