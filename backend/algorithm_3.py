"""Algorithm 3 coordinator — fuse Transformer (Khối 1) + PDR (Khối 2) + ESKF (Khối 3).

Đây là tầng ĐIỀU PHỐI runtime cho algorithm 3:
- IMU  -> PDRModel             -> StepEvent(Δx,Δy,σ) -> ESKF.predict   (motion model)
- RSSI -> TransformerPredictor -> Z_obs(x,y)         -> ESKF.update    (observation model)
- ESKF -> vị trí fused cuối cùng.

Hai luồng bất đồng bộ: gọi `process_imu()` cho mỗi mẫu IMU và `process_rssi()` cho
mỗi mẫu RSSI; mỗi cái tự kích hoạt predict/update khi đủ điều kiện.

Xem backend/algorithms/CLAUDE_algor3.md để hiểu tổng thể.
"""
from __future__ import annotations

import math
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Deque, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.algorithms.transformer import config as tf_config
from backend.algorithms.transformer.training.model_def import RSSITransformer
from backend.algorithms.pdr.pdr_model import PDRModel, StepEvent
from backend.algorithms.eskf.eskf_model import ESKF2D, ESKFState
from backend.run_history_csv import run_history_csv


RSSI_COLUMNS = [
    "wifi_rssi_1", "wifi_rssi_2", "wifi_rssi_3", "wifi_rssi_4",
    "ble_rssi_1", "ble_rssi_2", "ble_rssi_3", "ble_rssi_4",
]


def _select_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


class TransformerPredictor:
    """Load scaler + checkpoint Transformer và chạy inference cho 1 cửa sổ RSSI."""

    def __init__(self, model_dir: Path) -> None:
        model_dir = Path(model_dir)
        scaler_path = model_dir / "scaler.joblib"
        model_path = model_dir / "transformer_model.pt"
        if not scaler_path.exists() or not model_path.exists():
            raise FileNotFoundError(
                f"Thiếu scaler.joblib / transformer_model.pt trong {model_dir}"
            )
        self.device = _select_device()
        self.scaler = joblib.load(scaler_path)
        self.model = RSSITransformer().to(self.device)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()

    def predict_window(self, window: List[List[float]]) -> Tuple[float, float]:
        """Window [WINDOW_SIZE, 8] đã hợp lệ -> (x, y) tuyệt đối (m)."""
        # Dùng DataFrame có tên cột để khớp scaler (fit bằng DataFrame) -> tránh warning.
        frame = pd.DataFrame(window, columns=RSSI_COLUMNS)
        scaled = self.scaler.transform(frame)
        scaled = np.clip(scaled, 0.0, 1.0)  # giữ input trong phân phối train
        tensor = torch.tensor(scaled, dtype=torch.float32, device=self.device).unsqueeze(0)
        with torch.no_grad():
            pred = self.model(tensor).detach().cpu().numpy()[0]
        return float(pred[0]), float(pred[1])


@dataclass
class Algorithm3State:
    """Trạng thái tổng hợp để runtime/UI đọc."""

    fused_x: float
    fused_y: float
    pos_std: float
    step_count: int
    update_count: int
    rejected_count: int
    last_obs: Optional[Tuple[float, float]]   # observation Transformer gần nhất
    last_step: Optional[Tuple[float, float]]  # displacement PDR gần nhất


class Algorithm3:
    """Điều phối Transformer + PDR + ESKF cho một tag/người dùng."""

    def __init__(
        self,
        model_dir: Optional[Path],
        start_x: float,
        start_y: float,
        offset_angle: float,
        offset_angle_bno: float,
        step_length_model: str = "weinberg",
        lowpass_cutoff_hz: Optional[float] = None,
        use_acc_magnitude: bool = False,
        predictor: Optional["TransformerPredictor"] = None,
    ) -> None:
        # Cho phép DÙNG CHUNG một TransformerPredictor đã load giữa nhiều tag/người
        # dùng trong cùng một lượt chạy (tránh load lại model torch n lần).
        if predictor is not None:
            self.predictor = predictor
        elif model_dir is not None:
            self.predictor = TransformerPredictor(model_dir)
        else:
            raise ValueError("Algorithm3 cần model_dir hoặc predictor")

        pdr_kwargs = dict(
            offset_angle=offset_angle,
            offset_angle_bno=offset_angle_bno,
            step_length_model=step_length_model,
            use_acc_magnitude=use_acc_magnitude,
        )
        if lowpass_cutoff_hz is not None:
            pdr_kwargs["lowpass_cutoff_hz"] = lowpass_cutoff_hz
        self.pdr = PDRModel(**pdr_kwargs)

        self.eskf = ESKF2D(x0=start_x, y0=start_y)

        self.window_size = tf_config.WINDOW_SIZE
        self.step_size = tf_config.STEP_SIZE
        self._rssi_window: Deque[List[float]] = deque(maxlen=self.window_size)
        self._rssi_counter = 0

        self.last_obs: Optional[Tuple[float, float]] = None
        self.last_step: Optional[Tuple[float, float]] = None

    # ------------------------------------------------------------------
    @staticmethod
    def _rssi_valid(values: List[float]) -> bool:
        """Chỉ chấp nhận mẫu có cả 8 kênh trong dải hợp lệ [-99, -1] (như training)."""
        for v in values:
            if v is None or not math.isfinite(v):
                return False
            if v < tf_config.RSSI_VALID_MIN or v > tf_config.RSSI_VALID_MAX:
                return False
        return True

    # ------------------------------------------------------------------
    def process_imu(
        self,
        acc_z: float,
        yaw: float,
        timestamp: float,
        acc_x: Optional[float] = None,
        acc_y: Optional[float] = None,
    ) -> Optional[StepEvent]:
        """Nạp 1 mẫu IMU. Nếu phát hiện bước -> ESKF.predict và trả StepEvent."""
        event = self.pdr.process_imu_stream(acc_z, yaw, timestamp, acc_x, acc_y)
        if event is not None:
            self.eskf.predict(
                delta_x=event.delta_x,
                delta_y=event.delta_y,
                sigma_step=event.sigma_step,
                sigma_heading_deg=event.sigma_heading_deg,
                step_length=event.step_length,
            )
            self.last_step = (event.delta_x, event.delta_y)
        return event

    def process_rssi(
        self,
        rssi_values: List[float],
        timestamp: float,
    ) -> Optional[Tuple[float, float, bool]]:
        """Nạp 1 mẫu RSSI (8 kênh). Khi đủ cửa sổ + tới nhịp downsample -> Transformer
        inference -> ESKF.update. Trả (z_x, z_y, accepted) nếu có update, None nếu không.

        Mẫu RSSI ngoài dải hợp lệ bị BỎ QUA (không nạp), khớp quy tắc training.
        """
        if not self._rssi_valid(rssi_values):
            return None

        self._rssi_window.append([float(v) for v in rssi_values])
        self._rssi_counter += 1

        if len(self._rssi_window) < self.window_size:
            return None
        if self._rssi_counter % self.step_size != 0:
            return None

        z_x, z_y = self.predictor.predict_window(list(self._rssi_window))
        accepted = self.eskf.update(z_x, z_y)
        self.last_obs = (z_x, z_y)
        return z_x, z_y, accepted

    # ------------------------------------------------------------------
    def get_state(self) -> Algorithm3State:
        s: ESKFState = self.eskf.get_state()
        return Algorithm3State(
            fused_x=s.x,
            fused_y=s.y,
            pos_std=s.pos_std,
            step_count=s.step_count,
            update_count=s.update_count,
            rejected_count=s.rejected_count,
            last_obs=self.last_obs,
            last_step=self.last_step,
        )


# ======================================================================
# Algorithm3Manager — bộ não điều phối runtime cho MỘT lượt chạy nhiều tag.
# ----------------------------------------------------------------------
# Đây là tầng quản lý trung tâm của thuật toán 3 (như mô tả spec): nó
#   - giữ một TransformerPredictor DÙNG CHUNG (load 1 lần / lượt chạy),
#   - tạo một Algorithm3 cho mỗi thiết bị (tag) đã chọn,
#   - nhận mẫu RSSI+IMU từ tầng truyền thông (mqtt_handle/transformer_pdr_eskf),
#   - trả về vị trí fused + telemetry cho endpoint polling và cho việc publish
#     user_pos về thiết bị.
# Engine lan/dập lửa + tính điểm (Pha B) sẽ cắm thêm vào đây sau.
# ======================================================================


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _imu_timestamp_ms(sample: Dict[str, Any]) -> float:
    """Chuyển timestamp mẫu MQTT sang milliseconds cho PDR.

    PDR so sánh delta_t với MIN/MAX_STEP_TIME (100–600 ms). Trước đây feed() dùng
    time.time() (giây) nên không bao giờ xác nhận bước. Không có field -> wall ms.
    """
    raw = _to_float(sample.get("timestamp"))
    if raw is None:
        return time.time() * 1000.0
    # Đã là epoch ms (~1e12); epoch giây (~1e9) -> ms; nhỏ hơn = synthetic/test ms.
    if raw >= 1e12:
        return raw
    if raw >= 1e9:
        return raw * 1000.0
    return raw


def _normalize_hex(value: str) -> str:
    value = str(value).strip().lower()
    if not value.startswith("0x"):
        value = f"0x{value}"
    return value


def _yaw_map_deg(
    yaw_raw: Optional[float],
    map_offset_angle: float,
    offset_angle_bno: float,
) -> Optional[float]:
    """Hướng map cho UI/sim — cùng công thức PDR (adjusted_yaw)."""
    if yaw_raw is None:
        return None
    return (float(yaw_raw) - float(map_offset_angle) - float(offset_angle_bno)) % 360.0


# Thiết bị ADMIN ảo (không có trong DB, điều khiển trực tiếp trên màn hình server).
ADMIN_HEX = "0xAD"
ADMIN_NAME = "ADMIN"


@dataclass
class _TagRuntime:
    """Một thiết bị/người dùng trong lượt chạy: bộ fusion + telemetry mới nhất."""

    tag_hex_id: str
    algo: Algorithm3
    device_id: Optional[int] = None
    device_name: Optional[str] = None
    yaw_raw: Optional[float] = None
    valve_open: Optional[float] = None
    valve_mode: Optional[float] = None
    button_a: Optional[bool] = None
    button_b: Optional[bool] = None
    button_c: Optional[bool] = None
    last_step_length: Optional[float] = None
    last_update_unix: Optional[float] = None


@dataclass
class Algorithm3RunState:
    """Trạng thái của một lượt chạy realtime algorithm 3."""

    run_id: str
    map_id: int
    map_offset_angle: float
    length_x: int
    width_y: int
    offset_angle_bno: float
    predictor: TransformerPredictor
    tags: Dict[str, _TagRuntime] = field(default_factory=dict)
    is_active: bool = True
    lock: Lock = field(default_factory=Lock)
    simulation: Optional[SessionSimulation] = None   # Pha B (None nếu creative)
    admin_enabled: bool = False
    # Trạng thái ADMIN ảo (frontend đẩy lên): x, y, yaw_map, valve_open, valve_mode, visible.
    admin_state: Optional[Dict[str, Any]] = None


class Algorithm3Manager:
    """Quản lý nhiều lượt chạy algorithm 3 (mỗi training_run_id một lượt)."""

    def __init__(self) -> None:
        self.runs: Dict[str, Algorithm3RunState] = {}

    # ------------------------------------------------------------------
    def start_run(
        self,
        run_id: str,
        map_id: int,
        map_offset_angle: float,
        length_x: int,
        width_y: int,
        model_dir: Path,
        device_meta: List[Dict[str, Any]],
        offset_angle_bno: float,
        start_x: float,
        start_y: float,
        root_fires: Optional[List[Dict[str, Any]]] = None,
        duration_seconds: int = 0,
        assembly_point: Optional[Tuple[int, int]] = None,
        admin_enabled: bool = False,
    ) -> None:
        """Khởi tạo lượt chạy: load model 1 lần, tạo Algorithm3 cho mỗi thiết bị.

        device_meta: list các dict {device_id, device_name, device_hex_id}.
        root_fires/duration_seconds: nếu có session -> tạo SessionSimulation (Pha B).
        """
        predictor = TransformerPredictor(model_dir)
        run = Algorithm3RunState(
            run_id=run_id,
            map_id=map_id,
            map_offset_angle=float(map_offset_angle),
            length_x=int(length_x),
            width_y=int(width_y),
            offset_angle_bno=float(offset_angle_bno),
            predictor=predictor,
        )

        for meta in device_meta:
            hex_id = _normalize_hex(meta["device_hex_id"])
            algo = Algorithm3(
                model_dir=None,
                start_x=float(start_x),
                start_y=float(start_y),
                offset_angle=float(map_offset_angle),
                offset_angle_bno=float(offset_angle_bno),
                predictor=predictor,
            )
            run.tags[hex_id] = _TagRuntime(
                tag_hex_id=hex_id,
                algo=algo,
                device_id=meta.get("device_id"),
                device_name=meta.get("device_name"),
            )

        # Thiết bị ADMIN ảo (nếu bật): khởi tạo ở tâm map, tham gia tính điểm/dập lửa.
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
        if duration_seconds and duration_seconds > 0 or root_fires:
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
    def feed(
        self, run_id: str, tag_hex: str, sample: Dict[str, Any]
    ) -> Optional[Tuple[float, float]]:
        """Nạp một mẫu reality (RSSI + IMU + valve) cho một tag.

        sample keys: rssi(list[8] | None), acc_x/acc_y/acc_z, yaw, valve_open,
        valve_mode, button_a/b/c, timestamp(optional).

        Trả (x, y) fused MỚI nếu vị trí thay đổi (để publish user_pos), None nếu không.
        """
        run = self.runs.get(run_id)
        if not run or not run.is_active:
            return None

        tag_hex = _normalize_hex(tag_hex)
        with run.lock:
            tag = run.tags.get(tag_hex)
            if tag is None:
                return None

            ts = _imu_timestamp_ms(sample)

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
            tag.last_update_unix = time.time()

            position_changed = False

            acc_z = _to_float(sample.get("acc_z"))
            if acc_z is not None and yaw is not None:
                event = tag.algo.process_imu(
                    acc_z, yaw, ts,
                    _to_float(sample.get("acc_x")),
                    _to_float(sample.get("acc_y")),
                )
                if event is not None:
                    tag.last_step_length = event.step_length
                    position_changed = True

            rssi = sample.get("rssi")
            if isinstance(rssi, (list, tuple)) and len(rssi) == 8:
                result = tag.algo.process_rssi([_to_float(v) for v in rssi], ts)
                if result is not None and result[2]:  # accepted update moved the state
                    position_changed = True

            if not position_changed:
                return None

            state = tag.algo.get_state()
            cx, cy = self._corrected_position(run, state.fused_x, state.fused_y)
            if run_history_csv.is_active(run_id):
                yaw_map = _yaw_map_deg(tag.yaw_raw, run.map_offset_angle, run.offset_angle_bno)
                run_history_csv.record(run_id, tag_hex, cx, cy, yaw_map)
            return cx, cy

    # ------------------------------------------------------------------
    def tick_simulation(self, run_id: str, dt: float) -> Optional[Dict[str, Any]]:
        """Bước mô phỏng 1 nhịp (gọi từ vòng lặp asyncio). Trả kết quả để publish.

        result: {map_changed, fires, ended, outcome} hoặc None nếu không có sim.
        """
        run = self.runs.get(run_id)
        if not run or not run.is_active or run.simulation is None:
            return None
        with run.lock:
            snapshot: Dict[str, Dict[str, Any]] = {}
            for hex_id, tag in run.tags.items():
                st = tag.algo.get_state()
                yaw_map = _yaw_map_deg(tag.yaw_raw, run.map_offset_angle, run.offset_angle_bno) or 0.0
                cx, cy = self._corrected_position(run, st.fused_x, st.fused_y)
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
    def _corrected_position(self, run: Algorithm3RunState, x: float, y: float) -> Tuple[float, float]:
        """'Tọa độ hiệu chỉnh': kéo điểm về trong biên map (chỉ trục nào sai).

        x<0 -> 0.1 ; x>X -> X-0.1 ; tương tự y. Dùng cho hiển thị + user_pos + mô phỏng.
        KHÔNG đổi trạng thái ESKF nội bộ (thuật toán giữ nguyên).
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
    def _cell_index(self, run: Algorithm3RunState, x: float, y: float) -> Optional[int]:
        col = int(math.floor(x))
        row = int(math.floor(y))
        if col < 0 or col >= run.length_x or row < 0 or row >= run.width_y:
            return None
        return row * run.length_x + col + 1

    def get_state(self, run_id: str) -> Dict[str, Any]:
        run = self.runs.get(run_id)
        if not run:
            raise ValueError("Algorithm 3 run not found")

        with run.lock:
            sim = run.simulation
            tags_out: List[Dict[str, Any]] = []
            for tag in run.tags.values():
                st = tag.algo.get_state()
                ds = (sim.device_state(tag.tag_hex_id) if sim
                      else {"score": None, "water_remaining": None,
                            "fires_extinguished": None, "disqualified": None})
                yaw_map = _yaw_map_deg(tag.yaw_raw, run.map_offset_angle, run.offset_angle_bno)
                spray_mode = None
                if tag.valve_mode is not None:
                    spray_mode = "spread" if tag.valve_mode <= 50 else "jet"
                cx, cy = self._corrected_position(run, st.fused_x, st.fused_y)
                tags_out.append({
                    "tag_hex_id": tag.tag_hex_id,
                    "device_id": tag.device_id,
                    "device_name": tag.device_name,
                    "is_admin": False,
                    "position_x": round(cx, 3),
                    "position_y": round(cy, 3),
                    "pos_std": round(st.pos_std, 3),
                    "cell_index": self._cell_index(run, cx, cy),
                    "yaw_raw": round(tag.yaw_raw, 2) if tag.yaw_raw is not None else None,
                    "yaw_map": round(yaw_map, 2) if yaw_map is not None else None,
                    "step_length": round(tag.last_step_length, 3) if tag.last_step_length is not None else None,
                    "valve_open": tag.valve_open,
                    "valve_mode": tag.valve_mode,
                    "spray_mode": spray_mode,
                    "button_a": tag.button_a,
                    "button_b": tag.button_b,
                    "button_c": tag.button_c,
                    "step_count": st.step_count,
                    "update_count": st.update_count,
                    "rejected_count": st.rejected_count,
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
                    "pos_std": None, "cell_index": self._cell_index(run, ax, ay),
                    "yaw_raw": None, "yaw_map": round(a.get("yaw_map", 0.0), 2),
                    "step_length": None,
                    "valve_open": a.get("valve_open", 0.0), "valve_mode": a.get("valve_mode", 0.0),
                    "spray_mode": "spread" if a.get("valve_mode", 0.0) <= 50 else "jet",
                    "button_a": None, "button_b": None, "button_c": None,
                    "step_count": None, "update_count": None, "rejected_count": None,
                    "last_update_unix": None,
                    "score": a_ds.get("score"), "water_remaining": a_ds.get("water_remaining"),
                    "water_capacity": a_ds.get("water_capacity"),
                    "fires_extinguished": a_ds.get("fires_extinguished"),
                    "disqualified": a_ds.get("disqualified"),
                })

            return {
                "training_run_id": run.run_id,
                "map_id": run.map_id,
                "map_offset_angles": run.map_offset_angle,
                "offset_angle_bno": run.offset_angle_bno,
                "is_active": run.is_active,
                "tags": tags_out,
                # --- Pha B: trạng thái lửa + kết thúc ---
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


# Singleton dùng chung cho server.
algorithm3_manager = Algorithm3Manager()
