"""Positioning utilities for trilateration Levenberg-Marquardt."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np

from backend.algorithms.trilateration_LM.engine import solve_trilateration_lm
from backend.algorithms.trilateration_LM.distance_kalman import DistanceKalmanFilterBank


@dataclass
class KalmanFilter2D:
    """Simple 2D Kalman filter for smoothing x/y estimates.

    State model (2D random walk):
        x_k = x_{k-1} + w_k,    w_k ~ N(0, Q)
        z_k = x_k + v_k,        v_k ~ N(0, R)

    Where x_k, z_k are 2x1 vectors [x, y]^T and Q, R, P are 2x2 matrices.

    Matrix equations:
        Prediction:
            x^-_k = x_{k-1}
            P^-_k = P_{k-1} + Q

        Gain:
            K_k = P^-_k (P^-_k + R)^{-1}

        Update:
            x_k = x^-_k + K_k (z_k - x^-_k)
            P_k = (I - K_k) P^-_k
    """

    # Scalar used to build Q = process_noise * I_2
    process_noise: float = 0.1
    # Scalar used to build R = measurement_noise * I_2
    measurement_noise: float = 0.5
    # Q: process covariance matrix
    Q: np.ndarray = field(init=False)
    # R: measurement covariance matrix
    R: np.ndarray = field(init=False)
    # P: estimation-error covariance matrix
    P: np.ndarray = field(init=False)
    # x: state estimate vector
    x: Optional[np.ndarray] = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.Q = np.eye(2) * self.process_noise
        self.R = np.eye(2) * self.measurement_noise
        self.P = np.eye(2)

    def update(self, measurement: np.ndarray) -> np.ndarray:
        if self.x is None:
            self.x = measurement.astype(float)
            return self.x

        x_pred = self.x
        p_pred = self.P + self.Q
        kalman_gain = p_pred @ np.linalg.inv(p_pred + self.R)
        self.x = x_pred + kalman_gain @ (measurement - x_pred)
        self.P = (np.eye(2) - kalman_gain) @ p_pred
        return self.x


@dataclass
class TrilaterationPositioning:
    """Combines raw-range filtering, LM solving, and Kalman smoothing."""

    min_beacons: int = 3
    use_kalman: bool = False
    # Position Kalman parameters:
    #   Q_xy = process_noise * I_2
    #   R_xy = measurement_noise * I_2
    process_noise: float = 0.1
    measurement_noise: float = 0.5
    use_distance_kalman: bool = True
    # Distance Kalman parameters (scalar per beacon):
    #   Q_d = distance_process_variance
    #   R_d = distance_measurement_variance
    #   P_d,0 = distance_initial_error_variance
    #   innovation gate on |nu_k| via distance_innovation_gate, nu_k = z_k - x^-_k
    distance_process_variance: float = 0.001
    distance_measurement_variance: float = 0.055
    distance_initial_error_variance: float = 1.0
    distance_innovation_gate: float = 0.9
    min_distance_m: float = 0.10
    max_distance_m: float = 15.0
    distance_filter: DistanceKalmanFilterBank = field(init=False)
    kalman: Optional[KalmanFilter2D] = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.distance_filter = DistanceKalmanFilterBank(
            process_variance=self.distance_process_variance,
            measurement_variance=self.distance_measurement_variance,
            initial_error_variance=self.distance_initial_error_variance,
            innovation_gate=self.distance_innovation_gate,
        )
        if self.use_kalman:
            self.kalman = KalmanFilter2D(
                process_noise=self.process_noise,
                measurement_noise=self.measurement_noise,
            )

    def compute_position(
        self,
        beacon_positions: Dict[str, Tuple[float, float]],
        raw_distances_cm: Dict[str, float],
    ) -> Optional[Dict[str, float]]:
        """Compute a filtered tag position from raw MQTT ranges in centimeters."""

        filtered_distances_m: Dict[str, float] = {}
        for beacon_hex_id, distance_cm in raw_distances_cm.items():
            try:
                distance_m = float(distance_cm) / 100.0
            except (TypeError, ValueError):
                continue

            if distance_m < self.min_distance_m:
                continue

            if distance_m > self.max_distance_m:
                continue

            if beacon_hex_id not in beacon_positions:
                continue

            if self.use_distance_kalman:
                filtered = self.distance_filter.filter(beacon_hex_id, distance_m)
            else:
                filtered = distance_m

            if filtered is None:
                continue

            filtered_distances_m[beacon_hex_id] = float(filtered)

        if len(filtered_distances_m) < self.min_beacons:
            return None

        solved = solve_trilateration_lm(beacon_positions, filtered_distances_m)
        if not solved:
            return None

        x, y, rms_error = solved
        if self.kalman is not None:
            filtered_xy = self.kalman.update(np.array([x, y], dtype=float))
            x, y = float(filtered_xy[0]), float(filtered_xy[1])

        return {
            "x": float(x),
            "y": float(y),
            "error": float(rms_error),
            "num_beacons": len(filtered_distances_m),
            "filtered_distances_cm": {beacon_hex_id: float(distance_m * 100.0) for beacon_hex_id, distance_m in filtered_distances_m.items()},
        }