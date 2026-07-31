"""Tính điểm người dùng (Pha B). TẤT CẢ THAM SỐ ĐẶT Ở ĐẦU FILE.

Quy tắc đã chốt với người dùng:
- Bắt đầu INITIAL_SCORE; không giới hạn trên. Điểm CHẶN SÀN ở 0 (không âm).
- Đi vào ô lửa: −(level × PENALTY_PER_LEVEL_PER_SEC) mỗi giây.
- Truất quyền (khoá điểm 0 + nước 0 vĩnh viễn) khi ở trong lửa LIÊN TỤC
  > DQ_FIRE_SECONDS (bộ đếm reset khi rời khỏi lửa).
  (Bật USE_SPEC_INSTANT_DQ=True để quay lại spec gốc: âm điểm là loại ngay.)
- Điểm dập lửa = 2 phần TÁCH BIỆT, CỘNG DỒN:
    (a) tăng dần: mỗi mức cường độ giảm được = POINTS_PER_LEVEL (gốc + lan).
    (b) thưởng hoàn thành (chỉ khi ô về 0):
        - lửa lan / lửa gốc đã lan > ROOT_SPREAD_GRACE lần: SPREAD_FIRE_COMPLETION.
        - lửa gốc (spread_count ≤ ROOT_SPREAD_GRACE):
              (ROOT_SPREAD_GRACE − spread_count)·ROOT_SPREAD_BONUS
            + original_level·ROOT_INTENSITY_BONUS.
- Dập chung: điểm của ô chia ĐỀU cho N thiết bị đang phun trúng (simulator xử lý).
- Kết thúc thành công: + thời_gian_còn_lại × TIME_REMAINING_BONUS_PER_SEC cho mọi
  thiết bị non-DQ. Hết giờ mà còn lửa → tất cả về 0 (simulator xử lý).
"""
from __future__ import annotations

# --- Điểm khởi tạo & phạt ---
INITIAL_SCORE = 1000
SCORE_FLOOR = 0
PENALTY_PER_LEVEL_PER_SEC = 100.0      # đi vào lửa: −level×100 mỗi giây

# --- Truất quyền ---
DQ_FIRE_SECONDS = 5.0                   # ở trong lửa LIÊN TỤC > ngưỡng -> loại (reset khi rời)
USE_SPEC_INSTANT_DQ = False             # True = đúng spec gốc (âm điểm là loại ngay)

# --- Điểm dập lửa ---
POINTS_PER_LEVEL = 20                   # mỗi mức cường độ giảm được
SPREAD_FIRE_COMPLETION = 100            # thưởng dập tắt 1 ô lửa lan
ROOT_SPREAD_GRACE = 5                   # ngưỡng số lần lan của lửa gốc
ROOT_SPREAD_BONUS = 1000               # ×(grace − spread_count)
ROOT_INTENSITY_BONUS = 200             # ×original_level

# --- Thưởng thời gian ---
TIME_REMAINING_BONUS_PER_SEC = 100


def fire_penalty(level: int, dt: float) -> float:
    """Điểm bị trừ khi đứng trong ô lửa `level` trong `dt` giây (giá trị âm)."""
    return -float(level) * PENALTY_PER_LEVEL_PER_SEC * dt


def extinguish_points(event: dict) -> float:
    """Tổng điểm của một sự kiện dập lửa (TRƯỚC khi chia cho số thiết bị)."""
    points = event.get("levels_reduced", 0) * POINTS_PER_LEVEL
    if event.get("reached_zero"):
        is_root = event.get("is_root")
        spread_count = int(event.get("spread_count", 0))
        if is_root and spread_count <= ROOT_SPREAD_GRACE:
            points += (ROOT_SPREAD_GRACE - spread_count) * ROOT_SPREAD_BONUS
            points += int(event.get("original_level", 0)) * ROOT_INTENSITY_BONUS
        else:
            points += SPREAD_FIRE_COMPLETION
    return float(points)


def time_bonus(remaining_seconds: float) -> float:
    return max(0.0, remaining_seconds) * TIME_REMAINING_BONUS_PER_SEC


def clamp_score(score: float) -> float:
    return max(SCORE_FLOOR, score)
