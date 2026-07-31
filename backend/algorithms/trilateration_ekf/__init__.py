"""Algorithm 5 — Trilateration tightly-coupled EKF (UWB).

Nạp THẲNG range thô vào một EKF (state [x, y, vx, vy], CV) thay vì giải LS rồi mới
lọc. Measurement h(x)=||p - anchor|| phi tuyến -> cần Jacobian -> EKF.
Xem reference.txt (backend/algorithms/trilateration_LM/reference.txt) mục 5.
"""
from .ekf import TrilaterationEKF

__all__ = ["TrilaterationEKF"]
