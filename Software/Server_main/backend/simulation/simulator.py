"""SessionSimulation — ghép FireGrid + ExtinguishEngine + scoring cho một lượt chạy.

Được `Algorithm3Manager` giữ và `step(dt, device_snapshot)` mỗi tick (asyncio ~10Hz).
Vị trí/valve thiết bị do MQTT cấp (manager truyền vào qua `device_snapshot`).

Trả về mỗi tick: có thay đổi bản đồ lửa không (để publish fire_data), payload fires,
trạng thái kết thúc + điểm cuối.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from . import extinguish as ext
from . import scoring
from .extinguish import ExtinguishEngine, Sprayer
from .fire_spread import FireGrid


@dataclass
class DeviceSim:
    capacity: float = ext.WATER_MAX     # dung tích bình: -1 = VÔ HẠN; >=0 = hữu hạn
    score: float = scoring.INITIAL_SCORE
    water: float = ext.WATER_MAX        # nước hiện còn (được set = capacity khi khởi tạo)
    time_in_fire: float = 0.0
    disqualified: bool = False
    fires_extinguished: Set[Tuple[int, int]] = field(default_factory=set)
    last_in_fire: bool = False

    @property
    def infinite(self) -> bool:
        """Bình vô hạn (capacity < 0): không hao nước, luôn phun được."""
        return self.capacity < 0


class SessionSimulation:
    def __init__(
        self,
        length_x: int,
        width_y: int,
        root_fires: List[dict],
        duration_seconds: int,
        device_hexes: List[str],
        assembly_point: Optional[Tuple[int, int]] = None,
        device_water: Optional[Dict[str, float]] = None,
    ) -> None:
        self.fire = FireGrid(length_x, width_y, root_fires)
        self.extinguish = ExtinguishEngine()
        self.duration = float(duration_seconds or 0)
        self.assembly = assembly_point
        self.has_roots = len(root_fires) > 0
        self.elapsed = 0.0
        self.ended = False
        self.outcome: Optional[dict] = None
        # Dung tích bình mỗi thiết bị (hex -> capacity; -1 = vô hạn). Thiếu -> WATER_MAX.
        device_water = device_water or {}
        self.devices: Dict[str, DeviceSim] = {}
        for h in device_hexes:
            cap = float(device_water.get(h, ext.WATER_MAX))
            self.devices[h] = DeviceSim(capacity=cap, water=(cap if cap >= 0 else 0.0))
        self._needs_followup = False   # cần gửi tin "giảm fires_num" sau khi có ô vừa tắt

    # ------------------------------------------------------------------
    def set_assembly(self, x: int, y: int) -> None:
        self.assembly = (int(x), int(y))

    def _disqualify(self, dev: DeviceSim) -> None:
        dev.disqualified = True
        dev.score = 0.0
        dev.water = 0.0

    # ------------------------------------------------------------------
    def step(self, dt: float, device_snapshot: Dict[str, dict]) -> dict:
        if self.ended:
            return {"map_changed": False, "fires": None, "ended": True, "outcome": self.outcome}

        self.elapsed += dt
        t = self.elapsed
        map_changed = False
        map_changed |= self.fire.spawn_due(t)
        map_changed |= self.fire.step_spread(t)

        # --- Nước + nạp lại ở điểm tập kết (bình vô hạn: bỏ qua hao/nạp) ---
        for hex_id, dev in self.devices.items():
            if dev.disqualified:
                dev.water = 0.0
                continue
            if dev.infinite:
                continue
            snap = device_snapshot.get(hex_id)
            if not snap:
                continue
            valve_open = float(snap.get("valve_open") or 0.0)
            if valve_open > 0:
                dev.water = max(0.0, dev.water - ext.water_drain(valve_open, dt))
            if self.assembly is not None and self._in_cell(snap, self.assembly):
                dev.water = dev.capacity   # nạp đầy về dung tích của thiết bị

        # --- Dập lửa ---
        sprayers: List[Sprayer] = []
        for hex_id, snap in device_snapshot.items():
            dev = self.devices.get(hex_id)
            if not dev or dev.disqualified:
                continue
            valve_open = float(snap.get("valve_open") or 0.0)
            if valve_open > ext.VALVE_MIN_EFFECTIVE and (dev.infinite or dev.water > 0) and snap.get("x") is not None:
                sprayers.append(Sprayer(
                    hex_id=hex_id, x=float(snap["x"]), y=float(snap["y"]),
                    heading=float(snap.get("yaw_map") or 0.0),
                    valve_open=valve_open, valve_mode=float(snap.get("valve_mode") or 0.0),
                ))
        events = self.extinguish.step(t, dt, self.fire, sprayers)
        if events:
            map_changed = True

        # --- Điểm dập lửa (chia đều cho thiết bị đang phun trúng) ---
        for ev in events:
            pts = scoring.extinguish_points(ev)
            sprayer_hexes = [h for h in ev["sprayers"] if not self.devices[h].disqualified]
            if not sprayer_hexes:
                continue
            share = pts / len(sprayer_hexes)
            for h in sprayer_hexes:
                dev = self.devices[h]
                dev.score = scoring.clamp_score(dev.score + share)
                if ev["reached_zero"]:
                    dev.fires_extinguished.add((ev["x"], ev["y"]))

        # --- Phạt khi đứng trong lửa + truất quyền ---
        for hex_id, dev in self.devices.items():
            if dev.disqualified:
                continue
            snap = device_snapshot.get(hex_id)
            if not snap or snap.get("x") is None:
                dev.last_in_fire = False
                dev.time_in_fire = 0.0   # rời lửa -> reset (DQ tính LIÊN TỤC)
                continue
            cx = int(math.floor(float(snap["x"])))
            cy = int(math.floor(float(snap["y"])))
            level = self.fire.level_at(cx, cy)
            dev.last_in_fire = level > 0
            if level > 0:
                dev.time_in_fire += dt
                new_score = dev.score + scoring.fire_penalty(level, dt)
                if scoring.USE_SPEC_INSTANT_DQ and new_score < scoring.SCORE_FLOOR:
                    self._disqualify(dev)
                    continue
                dev.score = scoring.clamp_score(new_score)
                if dev.time_in_fire > scoring.DQ_FIRE_SECONDS:
                    self._disqualify(dev)
            else:
                dev.time_in_fire = 0.0   # ra khỏi lửa -> reset bộ đếm liên tục

        # --- Kiểm tra kết thúc ---
        self._check_end(t)

        # --- Payload fires: đúng spec.
        # Tin chứa ô vừa tắt VẪN đếm ô đó trong fires_num (gửi kèm level=0);
        # tin KẾ TIẾP mới bỏ ô và giảm fires_num.
        active = self.fire.fires_payload()                 # các ô level > 0
        just_died = [{"x": c.x, "y": c.y, "level": 0}
                     for c in self.fire.cells.values() if c.level <= 0]
        self.fire.remove_dead()

        if just_died:
            fires_payload = active + just_died
            fires_num = len(active) + len(just_died)        # tin này VẪN đếm ô vừa tắt
            self._needs_followup = True
            publish = True
        elif self._needs_followup:
            fires_payload = active                          # tin kế: đã bỏ ô -> giảm fires_num
            fires_num = len(active)
            self._needs_followup = False
            publish = True
        else:
            fires_payload = active
            fires_num = len(active)
            publish = map_changed

        return {
            "map_changed": publish,
            "fires": fires_payload if publish else None,
            "fires_num": fires_num,
            "ended": self.ended,
            "outcome": self.outcome,
        }

    # ------------------------------------------------------------------
    def _in_cell(self, snap: dict, cell: Tuple[int, int]) -> bool:
        if snap.get("x") is None:
            return False
        return (int(math.floor(float(snap["x"]))) == cell[0]
                and int(math.floor(float(snap["y"]))) == cell[1])

    def _check_end(self, t: float) -> None:
        if self.ended:
            return
        active = self.fire.active_cells()

        if self.duration > 0 and t >= self.duration:
            if active:
                self._end(reason="timeout_fail", all_zero=True)
            else:
                self._end(reason="timeout_success", add_time_bonus=True)
            return

        # Kết thúc sớm: mọi gốc đã xuất hiện + tắt, và không còn ô lửa nào (kể cả lan).
        if self.has_roots and self.fire.all_roots_done() and not active:
            self._end(reason="cleared_success", add_time_bonus=True)

    def _end(self, reason: str, all_zero: bool = False, add_time_bonus: bool = False) -> None:
        self.ended = True
        remaining = max(0.0, self.duration - self.elapsed)
        for dev in self.devices.values():
            if all_zero:
                dev.score = 0.0
            elif add_time_bonus and not dev.disqualified:
                dev.score = scoring.clamp_score(dev.score + scoring.time_bonus(remaining))
        self.outcome = {
            "reason": reason,
            "remaining_seconds": round(remaining, 1),
            "final_scores": {h: int(round(d.score)) for h, d in self.devices.items()},
        }

    # ------------------------------------------------------------------
    def device_state(self, hex_id: str) -> dict:
        dev = self.devices.get(hex_id)
        if not dev:
            return {"score": None, "water_remaining": None, "water_capacity": None,
                    "fires_extinguished": None, "disqualified": None}
        if dev.disqualified:
            water_remaining = 0.0
        elif dev.infinite:
            water_remaining = -1.0          # -1 = vô hạn (frontend hiển thị ∞)
        else:
            water_remaining = round(dev.water, 1)
        return {
            "score": int(round(dev.score)),
            "water_remaining": water_remaining,
            "water_capacity": int(dev.capacity),    # -1 = vô hạn
            "fires_extinguished": len(dev.fires_extinguished),
            "disqualified": dev.disqualified,
        }

    def fires_state(self) -> List[dict]:
        """Mọi ô lửa đang cháy (gốc + lan) để vẽ realtime."""
        return self.fire.fires_payload()

    def root_panel(self) -> List[dict]:
        return self.fire.root_panel(self.elapsed)
