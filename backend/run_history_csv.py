"""CSV recorder for realtime training position history (algorithms 2, 3, 5)."""
from __future__ import annotations

import csv
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HISTORY_DIR = PROJECT_ROOT / "history_run"

FIELDNAMES = ["elapsed_s", "tag_hex_id", "position_x", "position_y", "yaw_map"]


@dataclass
class _Recorder:
    run_id: str
    map_id: int
    algorithm: int
    started_at: datetime
    rows: List[Dict[str, Any]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_snap: Dict[str, tuple] = field(default_factory=dict)


class RunHistoryCsv:
    """In-memory buffer per training run; flush to history_run/ on finalize."""

    def __init__(self) -> None:
        self._recorders: Dict[str, _Recorder] = {}
        self._global_lock = threading.Lock()

    def start(self, run_id: str, map_id: int, algorithm: int) -> None:
        with self._global_lock:
            self._recorders[run_id] = _Recorder(
                run_id=run_id,
                map_id=int(map_id),
                algorithm=int(algorithm),
                started_at=datetime.now(),
            )

    def is_active(self, run_id: str) -> bool:
        with self._global_lock:
            return run_id in self._recorders

    def record(
        self,
        run_id: str,
        tag_hex: str,
        position_x: float,
        position_y: float,
        yaw_map: Optional[float] = None,
    ) -> None:
        with self._global_lock:
            rec = self._recorders.get(run_id)
        if rec is None:
            return

        snap = (round(float(position_x), 4), round(float(position_y), 4))
        with rec.lock:
            if rec.last_snap.get(tag_hex) == snap:
                return
            rec.last_snap[tag_hex] = snap
            elapsed = (datetime.now() - rec.started_at).total_seconds()
            rec.rows.append({
                "elapsed_s": round(elapsed, 3),
                "tag_hex_id": str(tag_hex),
                "position_x": round(float(position_x), 4),
                "position_y": round(float(position_y), 4),
                "yaw_map": round(float(yaw_map), 2) if yaw_map is not None else "",
            })

    def finalize(self, run_id: str) -> Optional[Path]:
        with self._global_lock:
            rec = self._recorders.pop(run_id, None)
        if rec is None or not rec.rows:
            return None

        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        ts = rec.started_at.strftime("%d_%m_%Y_%H_%M_%S")
        path = HISTORY_DIR / f"map_{rec.map_id}_{ts}.csv"
        with rec.lock:
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerows(rec.rows)
        return path


run_history_csv = RunHistoryCsv()
