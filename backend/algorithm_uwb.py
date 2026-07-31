"""UWBManager — điều phối lượt chạy realtime cho thuật toán UWB (2 & 5).

Mirror `Algorithm3Manager` (backend/algorithm_3.py) nhưng định vị bằng UWB ranging,
KHÔNG dùng RSSI/PDR:
 - mỗi tag giữ một "brain" định vị: `Algorithm2` (loosely-coupled LM) hoặc
   `Algorithm5` (tightly-coupled EKF), chọn theo `algorithm` của lượt chạy;
 - range thô (cm) gom theo anchor -> brain.process_ranges(ranges_cm, dt) -> (x, y);
 - yaw/valve lấy từ topic `uwb_id/<tag>` (cho FOV + mô phỏng lửa), KHÔNG dùng để định vị;
 - dùng lại NGUYÊN `SessionSimulation` + thiết bị ADMIN ảo + "tọa độ hiệu chỉnh"
   (kéo về biên map) y hệt algo 3 — phần GỬI (user_pos/fire_data) cũng y hệt algo 3.

Đây là lớp điều phối (giống algorithm_3.py); lớp transport MQTT ở
backend/mqtt_handle/trilateration_uwb/runtime.py.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from backend.algorithm_2 import Algorithm2
from backend.algorithm_5 import Algorithm5
from backend.simulation.simulator import SessionSimulation
from backend.run_history_csv import run_history_csv


# Thiết bị ADMIN ảo (không có trong DB, điều khiển trực tiếp trên màn hình server).
ADMIN_HEX = "0xAD"
ADMIN_NAME = "ADMIN"


def _normalize_hex(value: str) -> str:
    value = str(value).strip().lower()
    if not value.startswith("0x"):
        value = f"0x{value}"
    return value


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class _UWBTag:
    """Một thiết bị/người dùng trong lượt chạy: brain định vị + telemetry mới nhất."""

    tag_hex_id: str
    brain: Any                                       # Algorithm2 | Algorithm5
    device_id: Optional[int] = None
    device_name: Optional[str] = None
    ranges_cm: Dict[str, float] = field(default_factory=dict)   # anchor_hex -> range (cm)
    last_solve_unix: Optional[float] = None
    solved_x: Optional[float] = None                 # vị trí thô (chưa hiệu chỉnh biên)
    solved_y: Optional[float] = None
    last_result: Dict[str, Any] = field(default_factory=dict)
    # Telemetry từ uwb_id (không dùng để định vị, chỉ FOV/valve/mô phỏng/chẩn đoán).
    yaw_raw: Optional[float] = None
    valve_open: Optional[float] = None
    valve_mode: Optional[float] = None
    button_a: Optional[bool] = None
    button_b: Optional[bool] = None
    button_c: Optional[bool] = None
    acc_magnitude: Optional[float] = None
    gyro_magnitude: Optional[float] = None
    last_update_unix: Optional[float] = None


@dataclass
class _UWBRun:
    """Trạng thái một lượt chạy realtime UWB (algo 2 hoặc 5)."""

    run_id: str
    algorithm: int
    map_id: int
    map_offset_angle: float
    length_x: int
    width_y: int
    beacons: List[Dict[str, Any]]
    tags: Dict[str, _UWBTag] = field(default_factory=dict)
    is_active: bool = True
    lock: Lock = field(default_factory=Lock)
    simulation: Optional[SessionSimulation] = None   # Pha B (None nếu creative)
    admin_enabled: bool = False
    admin_state: Optional[Dict[str, Any]] = None


class UWBManager:
    """Quản lý nhiều lượt chạy realtime UWB (mỗi training_run_id một lượt)."""

    def __init__(self) -> None:
        self.runs: Dict[str, _UWBRun] = {}

    # ------------------------------------------------------------------
    def start_run(
        self,
        run_id: str,
        algorithm: int,
        map_id: int,
        map_offset_angle: float,
        length_x: int,
        width_y: int,
        beacon_positions: Dict[str, Tuple[float, float]],
        beacons: List[Dict[str, Any]],
        device_meta: List[Dict[str, Any]],
        start_x: float,
        start_y: float,
        root_fires: Optional[List[Dict[str, Any]]] = None,
        duration_seconds: int = 0,
        assembly_point: Optional[Tuple[int, int]] = None,
        admin_enabled: bool = False,
    ) -> None:
        """Khởi tạo lượt chạy: tạo brain định vị (Algorithm2/5) cho mỗi thiết bị.

        device_meta: list dict {device_id, device_name, device_hex_id}.
        beacon_positions: {anchor_hex -> (x, y)} (mét) cho brain.
        root_fires/duration_seconds: có session -> tạo SessionSimulation (Pha B).
        """
        run = _UWBRun(
            run_id=run_id,
            algorithm=int(algorithm),
            map_id=map_id,
            map_offset_angle=float(map_offset_angle),
            length_x=int(length_x),
            width_y=int(width_y),
            beacons=beacons,
        )

        for meta in device_meta:
            hex_id = _normalize_hex(meta["device_hex_id"])
            brain = (Algorithm5(beacon_positions) if int(algorithm) == 5
                     else Algorithm2(beacon_positions))
            run.tags[hex_id] = _UWBTag(
                tag_hex_id=hex_id,
                brain=brain,
                device_id=meta.get("device_id"),
                device_name=meta.get("device_name"),
                solved_x=float(start_x),
                solved_y=float(start_y),
            )

        # Thiết bị ADMIN ảo (nếu bật): khởi tạo ở vị trí start, tham gia tính điểm/dập lửa.
        run.admin_enabled = bool(admin_enabled)
        if run.admin_enabled:
            run.admin_state = {
                "x": float(start_x), "y": float(start_y), "yaw_map": 0.0,
                "valve_open": 0.0, "valve_mode": 0.0, "visible": True,
            }

        # Dung tích bình mỗi thiết bị (hex -> capacity; -1 = vô hạn). Thiếu -> WATER_MAX (sim).
        device_water: Dict[str, float] = {}
        for meta in device_meta:
            cap = meta.get("water_capacity")
            if cap is not None:
                device_water[_normalize_hex(meta["device_hex_id"])] = float(cap)
        if run.admin_enabled:
            device_water[ADMIN_HEX] = -1.0      # ADMIN ảo: bình vô hạn

        # Tạo mô phỏng (lan/dập lửa + tính điểm) khi có session; creative -> None.
        root_fires = root_fires or []
        if (duration_seconds and duration_seconds > 0) or root_fires:
            device_hexes = list(run.tags.keys())
            if run.admin_enabled:
                device_hexes.append(ADMIN_HEX)
            run.simulation = SessionSimulation(
                length_x=int(length_x),
                width_y=int(width_y),
                root_fires=root_fires,
                duration_seconds=int(duration_seconds or 0),
                device_hexes=device_hexes,
                assembly_point=assembly_point,
                device_water=device_water,
            )

        self.runs[run_id] = run

    # ------------------------------------------------------------------
    def feed_range(
        self, run_id: str, tag_hex: str, anchor_hex: str, distance_cm: float
    ) -> Optional[Tuple[float, float]]:
        """Nạp MỘT range (anchor -> tag) cho 1 nhịp. Gom theo anchor rồi giải lại.

        Trả (x, y) hiệu chỉnh MỚI nếu giải được (để publish user_pos), None nếu không.
        """
        run = self.runs.get(run_id)
        if not run or not run.is_active:
            return None
        tag = run.tags.get(_normalize_hex(tag_hex))
        if tag is None:
            return None

        dist = _to_float(distance_cm)
        if dist is None:
            return None

        with run.lock:
            tag.ranges_cm[_normalize_hex(anchor_hex)] = dist
            now = time.time()
            dt = (now - tag.last_solve_unix) if tag.last_solve_unix else None
            tag.last_solve_unix = now
            tag.last_update_unix = now

            result = tag.brain.process_ranges(tag.ranges_cm, dt)
            if not result:
                return None
            tag.last_result = result
            sx = _to_float(result.get("x"))
            sy = _to_float(result.get("y"))
            if sx is None or sy is None:
                return None
            tag.solved_x, tag.solved_y = sx, sy
            cx, cy = self._corrected_position(run, sx, sy)
            if run_history_csv.is_active(run_id):
                yaw_map = (
                    (tag.yaw_raw - run.map_offset_angle) % 360.0
                    if tag.yaw_raw is not None else None
                )
                run_history_csv.record(run_id, tag_hex, cx, cy, yaw_map)
            return cx, cy

    def feed_user(self, run_id: str, tag_hex: str, sample: Dict[str, Any]) -> None:
        """Nạp telemetry uwb_id (yaw/valve/button/IMU) — KHÔNG ảnh hưởng định vị."""
        run = self.runs.get(run_id)
        if not run or not run.is_active:
            return
        tag = run.tags.get(_normalize_hex(tag_hex))
        if tag is None:
            return
        with run.lock:
            yaw = _to_float(sample.get("yaw"))
            if yaw is not None:
                tag.yaw_raw = yaw
            vopen = _to_float(sample.get("valve_open"))
            if vopen is not None:
                tag.valve_open = vopen
            vmode = _to_float(sample.get("valve_mode"))
            if vmode is not None:
                tag.valve_mode = vmode
            for key in ("button_a", "button_b", "button_c"):
                if sample.get(key) is not None:
                    setattr(tag, key, bool(sample[key]))
            am = _to_float(sample.get("acc_magnitude"))
            if am is not None:
                tag.acc_magnitude = am
            gm = _to_float(sample.get("gyro_magnitude"))
            if gm is not None:
                tag.gyro_magnitude = gm
            tag.last_update_unix = time.time()

    # ------------------------------------------------------------------
    def tick_simulation(self, run_id: str, dt: float) -> Optional[Dict[str, Any]]:
        """Bước mô phỏng 1 nhịp (gọi từ vòng lặp asyncio). Trả kết quả để publish.

        result: {map_changed, fires, fires_num, ended, outcome} hoặc None nếu không có sim.
        """
        run = self.runs.get(run_id)
        if not run or not run.is_active or run.simulation is None:
            return None
        with run.lock:
            snapshot: Dict[str, Dict[str, Any]] = {}
            for hex_id, tag in run.tags.items():
                yaw_map = (
                    (tag.yaw_raw - run.map_offset_angle) % 360.0
                    if tag.yaw_raw is not None else 0.0
                )
                cx, cy = self._corrected_position(run, tag.solved_x or 0.0, tag.solved_y or 0.0)
                snapshot[hex_id] = {
                    "x": cx, "y": cy, "yaw_map": yaw_map,
                    "valve_open": tag.valve_open or 0.0, "valve_mode": tag.valve_mode or 0.0,
                }
            # ADMIN ảo: vị trí/hướng/valve do frontend đẩy lên (set_admin_state).
            if run.admin_enabled and run.admin_state and run.admin_state.get("visible", True):
                a = run.admin_state
                ax, ay = self._corrected_position(run, a["x"], a["y"])
                snapshot[ADMIN_HEX] = {
                    "x": ax, "y": ay, "yaw_map": a.get("yaw_map", 0.0),
                    "valve_open": a.get("valve_open", 0.0), "valve_mode": a.get("valve_mode", 0.0),
                }
            return run.simulation.step(dt, snapshot)

    def get_device_score(self, run_id: str, tag_hex: str) -> int:
        """Điểm hiện tại của 1 thiết bị (để gắn vào user_pos). 0 nếu chưa có sim."""
        run = self.runs.get(run_id)
        if not run or run.simulation is None:
            return 0
        with run.lock:
            ds = run.simulation.device_state(_normalize_hex(tag_hex))
            return int(ds.get("score") or 0)

    def device_scores(self, run_id: str) -> List[Dict[str, Any]]:
        """[{device_id, score}] cuối cùng — để lưu session_history khi kết thúc."""
        run = self.runs.get(run_id)
        if not run or run.simulation is None:
            return []
        with run.lock:
            out = []
            for hex_id, tag in run.tags.items():
                ds = run.simulation.device_state(hex_id)
                out.append({"device_id": tag.device_id, "score": int(ds.get("score") or 0)})
            return out

    # ------------------------------------------------------------------
    def _corrected_position(self, run: _UWBRun, x: float, y: float) -> Tuple[float, float]:
        """'Tọa độ hiệu chỉnh': kéo điểm về trong biên map (chỉ trục nào sai).

        x<0 -> 0.1 ; x>X -> X-0.1 ; tương tự y. Dùng cho hiển thị + user_pos + mô phỏng.
        KHÔNG đổi trạng thái nội bộ của brain (thuật toán giữ nguyên) — y hệt algo 3.
        """
        cx, cy = float(x), float(y)
        if cx < 0:
            cx = 0.1
        elif cx > run.length_x:
            cx = run.length_x - 0.1
        if cy < 0:
            cy = 0.1
        elif cy > run.width_y:
            cy = run.width_y - 0.1
        return cx, cy

    def set_admin_state(self, run_id: str, state: Dict[str, Any]) -> None:
        """Cập nhật trạng thái ADMIN ảo (frontend đẩy lên mỗi nhịp khi điều khiển)."""
        run = self.runs.get(run_id)
        if not run or not run.admin_enabled:
            return
        with run.lock:
            cur = run.admin_state or {}
            cur.update({
                "x": float(state.get("x", cur.get("x", 0.0))),
                "y": float(state.get("y", cur.get("y", 0.0))),
                "yaw_map": float(state.get("yaw_map", cur.get("yaw_map", 0.0))),
                "valve_open": float(state.get("valve_open", cur.get("valve_open", 0.0))),
                "valve_mode": float(state.get("valve_mode", cur.get("valve_mode", 0.0))),
                "visible": bool(state.get("visible", cur.get("visible", True))),
            })
            run.admin_state = cur
            if run_history_csv.is_active(run_id):
                ax, ay = self._corrected_position(run, cur["x"], cur["y"])
                run_history_csv.record(
                    run_id, ADMIN_HEX, ax, ay, float(cur.get("yaw_map", 0.0))
                )

    # ------------------------------------------------------------------
    def _cell_index(self, run: _UWBRun, x: float, y: float) -> Optional[int]:
        col = int(math.floor(x))
        row = int(math.floor(y))
        if col < 0 or col >= run.length_x or row < 0 or row >= run.width_y:
            return None
        return row * run.length_x + col + 1

    def get_state(self, run_id: str) -> Dict[str, Any]:
        run = self.runs.get(run_id)
        if not run:
            raise ValueError("UWB run not found")

        with run.lock:
            sim = run.simulation
            tags_out: List[Dict[str, Any]] = []
            for tag in run.tags.values():
                ds = (sim.device_state(tag.tag_hex_id) if sim
                      else {"score": None, "water_remaining": None,
                            "fires_extinguished": None, "disqualified": None})
                yaw_map = (
                    (tag.yaw_raw - run.map_offset_angle) % 360.0
                    if tag.yaw_raw is not None else None
                )
                spray_mode = "spread" if (tag.valve_mode or 0.0) <= 50 else "jet"
                cx, cy = self._corrected_position(run, tag.solved_x or 0.0, tag.solved_y or 0.0)
                res = tag.last_result
                rms = _to_float(res.get("rms_error"))
                tags_out.append({
                    "tag_hex_id": tag.tag_hex_id,
                    "device_id": tag.device_id,
                    "device_name": tag.device_name,
                    "is_admin": False,
                    "position_x": round(cx, 3),
                    "position_y": round(cy, 3),
                    "raw_x": round(tag.solved_x, 3) if tag.solved_x is not None else None,
                    "raw_y": round(tag.solved_y, 3) if tag.solved_y is not None else None,
                    "cell_index": self._cell_index(run, cx, cy),
                    "yaw_raw": round(tag.yaw_raw, 2) if tag.yaw_raw is not None else None,
                    "yaw_map": round(yaw_map, 2) if yaw_map is not None else None,
                    "valve_open": tag.valve_open,
                    "valve_mode": tag.valve_mode,
                    "spray_mode": spray_mode,
                    "button_a": tag.button_a,
                    "button_b": tag.button_b,
                    "button_c": tag.button_c,
                    # --- chẩn đoán định vị UWB ---
                    "rms_error": round(rms, 4) if rms is not None else None,
                    "num_beacons": res.get("num_beacons"),
                    "ranges_accepted": res.get("ranges_accepted"),
                    "ranges_rejected": res.get("ranges_rejected"),
                    "ranges_cm": {h: round(v, 1) for h, v in tag.ranges_cm.items()},
                    "filtered_ranges_cm": res.get("filtered_distances_cm", {}),
                    "acc_magnitude": tag.acc_magnitude,
                    "gyro_magnitude": tag.gyro_magnitude,
                    "last_update_unix": tag.last_update_unix,
                    # --- Pha B (lan/dập lửa + tính điểm) ---
                    "score": ds.get("score"),
                    "water_remaining": ds.get("water_remaining"),
                    "water_capacity": ds.get("water_capacity"),
                    "fires_extinguished": ds.get("fires_extinguished"),
                    "disqualified": ds.get("disqualified"),
                })

            # ADMIN ảo: báo cáo điểm/nước từ sim (vị trí frontend tự vẽ từ local state).
            if run.admin_enabled and run.admin_state:
                a = run.admin_state
                ax, ay = self._corrected_position(run, a["x"], a["y"])
                a_ds = (sim.device_state(ADMIN_HEX) if sim
                        else {"score": None, "water_remaining": None,
                              "fires_extinguished": None, "disqualified": None})
                tags_out.append({
                    "tag_hex_id": ADMIN_HEX, "device_id": None, "device_name": ADMIN_NAME,
                    "is_admin": True, "visible": a.get("visible", True),
                    "position_x": round(ax, 3), "position_y": round(ay, 3),
                    "raw_x": round(ax, 3), "raw_y": round(ay, 3),
                    "cell_index": self._cell_index(run, ax, ay),
                    "yaw_raw": None, "yaw_map": round(a.get("yaw_map", 0.0), 2),
                    "valve_open": a.get("valve_open", 0.0), "valve_mode": a.get("valve_mode", 0.0),
                    "spray_mode": "spread" if a.get("valve_mode", 0.0) <= 50 else "jet",
                    "button_a": None, "button_b": None, "button_c": None,
                    "rms_error": None, "num_beacons": None,
                    "ranges_accepted": None, "ranges_rejected": None,
                    "ranges_cm": {}, "filtered_ranges_cm": {},
                    "acc_magnitude": None, "gyro_magnitude": None,
                    "last_update_unix": None,
                    "score": a_ds.get("score"), "water_remaining": a_ds.get("water_remaining"),
                    "water_capacity": a_ds.get("water_capacity"),
                    "fires_extinguished": a_ds.get("fires_extinguished"),
                    "disqualified": a_ds.get("disqualified"),
                })

            return {
                "training_run_id": run.run_id,
                "map_id": run.map_id,
                "algorithm": run.algorithm,
                "map_offset_angles": run.map_offset_angle,
                "is_active": run.is_active,
                "tags": tags_out,
                # --- Pha B: trạng thái lửa + kết thúc (y hệt algo 3) ---
                "fires": sim.fires_state() if sim else [],
                "root_fires": sim.root_panel() if sim else [],
                "elapsed": round(sim.elapsed, 1) if sim else None,
                "duration": sim.duration if sim else None,
                "ended": sim.ended if sim else False,
                "outcome": sim.outcome if sim else None,
            }

    # ------------------------------------------------------------------
    def stop_run(self, run_id: str) -> None:
        run = self.runs.get(run_id)
        if run:
            run.is_active = False

    def remove_run(self, run_id: str) -> None:
        self.stop_run(run_id)
        self.runs.pop(run_id, None)

    def has_run(self, run_id: str) -> bool:
        return run_id in self.runs


# Singleton dùng chung cho server (algo 2 & 5).
uwb_manager = UWBManager()
