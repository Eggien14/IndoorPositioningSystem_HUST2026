"""Trilateration solver primitives (Algorithm 2, loosely-coupled).

THAM SỐ TINH CHỈNH ở ĐẦU FILE.

Pipeline hình học (xem reference.txt mục 1-3, 8-9):
  lls_initial_position()      -> điểm khởi tạo dạng đóng (LLS), không phân kỳ.
  solve_trilateration_robust()-> LM damped (λ ADAPTIVE) + IRLS-Huber + (tuỳ chọn)
                                 trọng số WLS ngoài; trả (x, y) + covariance P.
`solve_trilateration_lm()` (cũ, unweighted) GIỮ LẠI cho đường chạy hiện tại.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np

# ----------------------------------------------------------------------------
# THAM SỐ TINH CHỈNH (solver)
# ----------------------------------------------------------------------------
MIN_BEACONS = 3                 # số anchor tối thiểu cho fix 2D
LM_MAX_ITER = 20                # số vòng lặp tối đa
LM_INITIAL_LAMBDA = 1e-2        # damping λ khởi tạo
LM_LAMBDA_DOWN = 0.7            # cost giảm -> λ *= (nhận bước, tiến về Gauss-Newton)
LM_LAMBDA_UP = 2.5              # cost tăng -> λ *= (loại bước, tiến về gradient descent)
LM_LAMBDA_MIN = 1e-7
LM_LAMBDA_MAX = 1e7
LM_CONVERGENCE_STEP_M = 1e-4    # |step| < ngưỡng -> hội tụ
HUBER_DELTA_M = 0.5             # ngưỡng residual robust (m): |r|<=δ trọng số 1, ngoài ra δ/|r|


def _collect(beacon_positions: Dict[str, Tuple[float, float]],
             tag_distances_m: Dict[str, float]):
    hexes, points, dists = [], [], []
    for beacon_hex, distance in tag_distances_m.items():
        beacon = beacon_positions.get(beacon_hex)
        if not beacon or distance is None or distance <= 0:
            continue
        hexes.append(beacon_hex)
        points.append((float(beacon[0]), float(beacon[1])))
        dists.append(float(distance))
    return hexes, np.asarray(points, dtype=float), np.asarray(dists, dtype=float)


def lls_initial_position(points: np.ndarray, distances: np.ndarray) -> Optional[np.ndarray]:
    """Linearized Least Squares (dạng đóng) -> điểm khởi tạo (x, y).

    Trừ phương trình của anchor THAM CHIẾU (chọn anchor gần nhất ~ dễ LoS) để khử
    số hạng x^2+y^2: 2(xi-xr)x + 2(yi-yr)y = (xi^2-xr^2)+(yi^2-yr^2)-(di^2-dr^2).
    Giải OLS p = (A^T A)^-1 A^T b. Trả None nếu suy biến.
    """
    n = len(points)
    if n < 3:
        return None
    ref = int(np.argmin(distances))           # anchor gần nhất làm tham chiếu
    xr, yr = points[ref]
    dr = distances[ref]
    rows, rhs = [], []
    for i in range(n):
        if i == ref:
            continue
        xi, yi = points[i]
        di = distances[i]
        rows.append([2.0 * (xi - xr), 2.0 * (yi - yr)])
        rhs.append((xi * xi - xr * xr) + (yi * yi - yr * yr) - (di * di - dr * dr))
    A = np.asarray(rows, dtype=float)
    b = np.asarray(rhs, dtype=float)
    try:
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    if not np.all(np.isfinite(sol)):
        return None
    return sol.astype(float)


def _huber_weights(residuals: np.ndarray, delta: float) -> np.ndarray:
    abs_r = np.abs(residuals)
    w = np.ones_like(abs_r)
    mask = abs_r > delta
    w[mask] = delta / np.maximum(abs_r[mask], 1e-9)
    return w


def solve_trilateration_robust(
    beacon_positions: Dict[str, Tuple[float, float]],
    tag_distances_m: Dict[str, float],
    prior_weights: Optional[Dict[str, float]] = None,
    initial_guess: Optional[Tuple[float, float]] = None,
    huber_delta: float = HUBER_DELTA_M,
    max_iter: int = LM_MAX_ITER,
) -> Optional[Dict[str, object]]:
    """Damped-LM (λ adaptive) + IRLS-Huber + WLS. Tối thiểu hoá Σ W_i (||p-a_i||-d_i)^2.

    prior_weights: trọng số WLS ngoài mỗi anchor (vd 1/variance từ distance Kalman).
    Trả dict {x, y, P(2x2 np.ndarray), rms, residuals{hex:r}, num_beacons} hoặc None.
    """
    hexes, points, distances = _collect(beacon_positions, tag_distances_m)
    if len(points) < MIN_BEACONS:
        return None

    # Trọng số WLS ngoài (mặc định = 1).
    if prior_weights:
        w_prior = np.asarray([float(prior_weights.get(h, 1.0)) for h in hexes], dtype=float)
        w_prior = np.where(np.isfinite(w_prior) & (w_prior > 0), w_prior, 1.0)
    else:
        w_prior = np.ones(len(hexes), dtype=float)

    # Điểm khởi tạo: tham số người dùng -> LLS -> centroid.
    if initial_guess is not None:
        est = np.asarray(initial_guess, dtype=float)
    else:
        est = lls_initial_position(points, distances)
        if est is None:
            est = points.mean(axis=0)

    def residuals_at(p):
        deltas = p - points
        norms = np.linalg.norm(deltas, axis=1)
        norms = np.where(norms < 1e-6, 1e-6, norms)
        return norms, deltas, norms - distances

    lam = LM_INITIAL_LAMBDA
    norms, deltas, res = residuals_at(est)
    w = w_prior * _huber_weights(res, huber_delta)
    cost = float(np.sum(w * res * res))

    last_JtWJ = None
    for _ in range(max_iter):
        jac = deltas / norms[:, np.newaxis]            # J_i = (p - a_i)/||p - a_i||
        W = w[:, np.newaxis]
        JtWJ = jac.T @ (W * jac)
        last_JtWJ = JtWJ
        grad = jac.T @ (w * res)
        try:
            step = np.linalg.solve(JtWJ + lam * np.eye(2), grad)
        except np.linalg.LinAlgError:
            break

        candidate = est - step
        c_norms, c_deltas, c_res = residuals_at(candidate)
        c_w = w_prior * _huber_weights(c_res, huber_delta)
        c_cost = float(np.sum(c_w * c_res * c_res))

        if c_cost < cost:
            # nhận bước, giảm damping (-> Gauss-Newton)
            est, norms, deltas, res, w, cost = candidate, c_norms, c_deltas, c_res, c_w, c_cost
            lam = max(LM_LAMBDA_MIN, lam * LM_LAMBDA_DOWN)
            if np.linalg.norm(step) < LM_CONVERGENCE_STEP_M:
                break
        else:
            # loại bước, tăng damping (-> gradient descent)
            lam = min(LM_LAMBDA_MAX, lam * LM_LAMBDA_UP)
            if lam >= LM_LAMBDA_MAX:
                break

    # Covariance hình học P = (J^T W J)^-1 (lớn khi GDOP xấu / trọng số nhỏ).
    if last_JtWJ is None:
        jac = deltas / norms[:, np.newaxis]
        last_JtWJ = jac.T @ (w[:, np.newaxis] * jac)
    try:
        P = np.linalg.pinv(last_JtWJ)
    except np.linalg.LinAlgError:
        P = np.eye(2)

    rms = float(np.sqrt(np.mean(res * res)))
    return {
        "x": float(est[0]),
        "y": float(est[1]),
        "P": P,
        "rms": rms,
        "residuals": {h: float(r) for h, r in zip(hexes, res)},
        "num_beacons": len(hexes),
    }


def solve_trilateration_lm(
    beacon_positions: Dict[str, Tuple[float, float]],
    tag_distances_m: Dict[str, float],
    max_iter: int = 12,
) -> Optional[Tuple[float, float, float]]:
    """[GIỮ NGUYÊN — dùng cho đường chạy cũ] damped Gauss-Newton unweighted.

    Returns (x, y, rms_error) or None if insufficient beacons.
    """
    valid_points = []
    valid_distances = []
    for beacon_hex, distance in tag_distances_m.items():
        beacon = beacon_positions.get(beacon_hex)
        if not beacon:
            continue
        if distance <= 0:
            continue
        valid_points.append(beacon)
        valid_distances.append(distance)

    if len(valid_points) < 3:
        return None

    points = np.asarray(valid_points, dtype=float)
    distances = np.asarray(valid_distances, dtype=float)

    estimate = points.mean(axis=0)
    damping = 1e-2

    for _ in range(max_iter):
        deltas = estimate - points
        norms = np.linalg.norm(deltas, axis=1)
        norms = np.where(norms < 1e-6, 1e-6, norms)

        residual = norms - distances
        jacobian = deltas / norms[:, np.newaxis]

        jt = jacobian.T
        hessian = jt @ jacobian + damping * np.eye(2)
        gradient = jt @ residual

        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            return None

        estimate = estimate - step

        if np.linalg.norm(step) < 1e-4:
            break

    final_delta = estimate - points
    final_norms = np.linalg.norm(final_delta, axis=1)
    rms_error = float(np.sqrt(np.mean((final_norms - distances) ** 2)))
    return float(estimate[0]), float(estimate[1]), rms_error
