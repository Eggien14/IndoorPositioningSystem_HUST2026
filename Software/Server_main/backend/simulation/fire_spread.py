"""FireGrid — bản đồ chỉ số ngọn lửa song song với bản đồ chính (Pha B).

Quản lý:
- Spawn ngọn lửa GỐC theo lịch (`fire_time_seconds` của session_fire).
- LAN lửa: mỗi `fire_spread_time` giây, MỌI ô đang cháy (level≥1) cộng `(level−1)`
  vào `fire_spread` ô kề ngẫu nhiên trong 8 ô (cap 5). Ô lan kế thừa đặc tính lan
  của nguồn; nếu nhiều nguồn dồn vào: `fire_spread_time` nhỏ nhất + `fire_spread` lớn nhất.
- Theo dõi trạng thái ngọn lửa gốc (cho bảng thông số + tính điểm): cường độ gốc,
  số lần đã lan, thời điểm bị dập tắt, thời gian tồn tại.

Toạ độ ô = góc dưới-trái (đồng nhất toàn dự án). Thời gian `t` tính bằng giây kể từ
lúc bấm Start (đồng bộ với lịch ngọn lửa).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --- Tham số tinh chỉnh ---
MAX_LEVEL = 5                 # mức cường độ tối đa
MIN_LEVEL = 0                 # 0 = đã tắt

Coord = Tuple[int, int]


@dataclass
class FireCell:
    x: int
    y: int
    level: int
    fire_spread: int           # số ô lan mỗi chu kỳ (0..8)
    fire_spread_time: int      # chu kỳ lan (giây); <=0 => không lan
    next_spread_at: float      # mốc thời gian lan kế tiếp (giây)
    is_root: bool = False
    root_id: Optional[int] = None     # session_fire_id nếu là gốc
    original_level: int = 0           # cường độ lúc spawn (gốc, để tính điểm)
    spread_count: int = 0             # số lần ô gốc đã lan (gốc)


@dataclass
class RootStatus:
    """Trạng thái 1 ngọn lửa gốc để hiển thị bảng + tính điểm."""
    root_id: int
    coord_x: int
    coord_y: int
    fire_time_seconds: int
    original_level: int
    fire_spread: int
    fire_spread_time: int
    appeared: bool = False
    appeared_at: Optional[float] = None
    extinguished_at: Optional[float] = None   # giây kể từ Start (None = chưa tắt)
    spread_count: int = 0
    current_level: int = 0
    done: bool = False                        # đã tắt hẳn, ngừng đếm/ngừng lan


class FireGrid:
    def __init__(self, length_x: int, width_y: int, root_fires: List[dict]) -> None:
        self.length_x = int(length_x)
        self.width_y = int(width_y)
        self.cells: Dict[Coord, FireCell] = {}

        # Trạng thái ngọn lửa gốc, khoá theo session_fire_id (hoặc index nếu thiếu).
        self.roots: Dict[int, RootStatus] = {}
        self._root_defs: List[dict] = []
        for i, f in enumerate(root_fires):
            rid = int(f.get("session_fire_id", i + 1))
            self.roots[rid] = RootStatus(
                root_id=rid,
                coord_x=int(f["coord_x"]),
                coord_y=int(f["coord_y"]),
                fire_time_seconds=int(f["fire_time_seconds"]),
                original_level=int(f["fire_level"]),
                fire_spread=int(f.get("fire_spread", 0)),
                fire_spread_time=int(f.get("fire_spread_time", 0)),
            )
            self._root_defs.append({**f, "session_fire_id": rid})

    # ------------------------------------------------------------------
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.length_x and 0 <= y < self.width_y

    def _neighbors(self, x: int, y: int) -> List[Coord]:
        out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if self.in_bounds(nx, ny):
                    out.append((nx, ny))
        return out

    def active_cells(self) -> List[FireCell]:
        return [c for c in self.cells.values() if c.level > 0]

    def level_at(self, x: int, y: int) -> int:
        c = self.cells.get((x, y))
        return c.level if c else 0

    def all_roots_done(self) -> bool:
        """True nếu mọi ngọn lửa gốc đã xuất hiện VÀ đã tắt hẳn."""
        return all(r.appeared and r.done for r in self.roots.values())

    def any_pending_root(self) -> bool:
        """Còn ngọn lửa gốc CHƯA xuất hiện (đang đợi tới giờ)."""
        return any(not r.appeared for r in self.roots.values())

    # ------------------------------------------------------------------
    def spawn_due(self, t: float) -> bool:
        """Spawn các ngọn lửa gốc tới giờ. Trả True nếu có thay đổi."""
        changed = False
        for rid, r in self.roots.items():
            if r.appeared or t < r.fire_time_seconds:
                continue
            r.appeared = True
            r.appeared_at = t
            r.current_level = r.original_level
            existing = self.cells.get((r.coord_x, r.coord_y))
            if existing:
                # Ô đã có lửa (do lan tới trước) -> nâng thành gốc, cộng cường độ.
                existing.level = min(MAX_LEVEL, max(existing.level, r.original_level))
                existing.is_root = True
                existing.root_id = rid
                existing.original_level = r.original_level
                existing.fire_spread = max(existing.fire_spread, r.fire_spread)
                if r.fire_spread_time > 0:
                    existing.fire_spread_time = (
                        min(existing.fire_spread_time, r.fire_spread_time)
                        if existing.fire_spread_time > 0 else r.fire_spread_time
                    )
                r.current_level = existing.level
            else:
                self.cells[(r.coord_x, r.coord_y)] = FireCell(
                    x=r.coord_x, y=r.coord_y, level=r.original_level,
                    fire_spread=r.fire_spread, fire_spread_time=r.fire_spread_time,
                    next_spread_at=t + r.fire_spread_time if r.fire_spread_time > 0 else float("inf"),
                    is_root=True, root_id=rid, original_level=r.original_level,
                )
            changed = True
        return changed

    # ------------------------------------------------------------------
    def step_spread(self, t: float) -> bool:
        """Thực hiện lan cho mọi ô tới chu kỳ. Trả True nếu bản đồ đổi."""
        changed = False
        # Chụp danh sách ô sẽ lan trước (tránh ô mới tạo lan ngay trong cùng vòng).
        spreaders = [c for c in self.cells.values()
                     if c.level > 0 and c.fire_spread > 0 and c.fire_spread_time > 0
                     and t >= c.next_spread_at]
        for src in spreaders:
            src.next_spread_at = t + src.fire_spread_time
            spread_value = src.level - 1
            if src.is_root and src.root_id in self.roots:
                self.roots[src.root_id].spread_count += 1
                src.spread_count += 1
            if spread_value <= 0:
                continue
            neighbors = self._neighbors(src.x, src.y)
            random.shuffle(neighbors)
            for (nx, ny) in neighbors[:src.fire_spread]:
                changed = True
                tgt = self.cells.get((nx, ny))
                if tgt is None:
                    self.cells[(nx, ny)] = FireCell(
                        x=nx, y=ny, level=min(MAX_LEVEL, spread_value),
                        fire_spread=src.fire_spread, fire_spread_time=src.fire_spread_time,
                        next_spread_at=t + src.fire_spread_time,
                    )
                else:
                    tgt.level = min(MAX_LEVEL, tgt.level + spread_value)
                    # Kế thừa đặc tính lan "mạnh nhất" khi bị dồn nhiều nguồn.
                    tgt.fire_spread = max(tgt.fire_spread, src.fire_spread)
                    if src.fire_spread_time > 0:
                        tgt.fire_spread_time = (
                            min(tgt.fire_spread_time, src.fire_spread_time)
                            if tgt.fire_spread_time > 0 else src.fire_spread_time
                        )
        if changed:
            self._sync_root_levels()
        return changed

    # ------------------------------------------------------------------
    def reduce_level(self, x: int, y: int, t: float, amount: int = 1) -> Tuple[int, int, bool]:
        """Giảm cường độ ô (do dập lửa). Trả (levels_reduced, new_level, reached_zero)."""
        c = self.cells.get((x, y))
        if not c or c.level <= 0:
            return 0, 0, False
        before = c.level
        c.level = max(MIN_LEVEL, c.level - amount)
        reduced = before - c.level
        reached_zero = c.level == 0
        if c.is_root and c.root_id in self.roots:
            self.roots[c.root_id].current_level = c.level
        if reached_zero:
            self._on_cell_dead(c, t)
        return reduced, c.level, reached_zero

    def _on_cell_dead(self, c: FireCell, t: float) -> None:
        if c.is_root and c.root_id in self.roots:
            r = self.roots[c.root_id]
            if not r.done:
                r.done = True
                r.current_level = 0
                r.extinguished_at = t
        # Ô chết sẽ được simulator gửi 1 lần level=0 rồi loại; ở đây chỉ hạ level.

    def remove_dead(self) -> None:
        """Loại các ô level 0 khỏi lưới (gọi SAU khi đã publish lần cuối)."""
        for key in [k for k, c in self.cells.items() if c.level <= 0]:
            del self.cells[key]

    def _sync_root_levels(self) -> None:
        for c in self.cells.values():
            if c.is_root and c.root_id in self.roots and not self.roots[c.root_id].done:
                self.roots[c.root_id].current_level = c.level

    # ------------------------------------------------------------------
    def fires_payload(self) -> List[dict]:
        """Danh sách mọi ô lửa (gốc + lan) đang có level>0 — để vẽ + publish."""
        return [
            {"x": c.x, "y": c.y, "level": c.level}
            for c in self.cells.values() if c.level > 0
        ]

    def root_panel(self, t: float) -> List[dict]:
        """Thông số ngọn lửa GỐC cho bảng (chỉ gốc, không gồm lan)."""
        out = []
        for r in self.roots.values():
            alive = None
            if r.appeared_at is not None:
                end = r.extinguished_at if r.extinguished_at is not None else t
                alive = round(end - r.appeared_at, 1)
            out.append({
                "root_id": r.root_id,
                "coord_x": r.coord_x,
                "coord_y": r.coord_y,
                "fire_time_seconds": r.fire_time_seconds,
                "original_level": r.original_level,
                "current_level": r.current_level if r.appeared else 0,
                "fire_spread": r.fire_spread,
                "fire_spread_time": r.fire_spread_time,
                "appeared": r.appeared,
                "extinguished_at": r.extinguished_at,
                "alive_time": alive,
                "spread_count": r.spread_count,
            })
        return out
