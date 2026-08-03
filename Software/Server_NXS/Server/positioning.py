"""
ToF/ToA (Time of Flight / Time of Arrival) Algorithm for UWB Indoor Positioning
=================================================================================

This module implements trilateration-based positioning using UWB distance measurements.
The algorithm includes:
1. Radius calibration to compensate for environmental factors
2. 2D/3D Trilateration using least squares optimization
3. Distance filtering and validation
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from scipy.optimize import least_squares
import logging

logger = logging.getLogger(__name__)


class RadiusCalibration:
    """
    Radius calibration for UWB distance measurements.
    Compensates for environmental factors affecting signal propagation.
    """
    
    def __init__(self, path_loss_exponent: float = 2.0):
        """
        Args:
            path_loss_exponent: Environmental path loss exponent (2.0 for free space, 
                              2.5-4.0 for indoor environments)
        """
        self.path_loss_exponent = path_loss_exponent
        self.calibration_factors = {}  # Beacon-specific calibration
        
    def calibrate_distance(self, beacon_id: str, measured_distance: float) -> float:
        """
        Apply calibration to measured distance.
        
        Args:
            beacon_id: Unique identifier of the beacon
            measured_distance: Raw distance measurement from UWB
            
        Returns:
            Calibrated distance in meters
        """
        # Apply beacon-specific calibration if available
        if beacon_id in self.calibration_factors:
            offset, scale = self.calibration_factors[beacon_id]
            return measured_distance * scale + offset
        
        # Default: return as-is (tag already calculated distance)
        return measured_distance
    
    def add_calibration(self, beacon_id: str, offset: float = 0.0, scale: float = 1.0):
        """
        Add calibration parameters for a specific beacon.
        
        Args:
            beacon_id: Beacon identifier
            offset: Distance offset in meters
            scale: Distance scaling factor
        """
        self.calibration_factors[beacon_id] = (offset, scale)


class Trilateration:
    """
    2D Trilateration using nonlinear least squares optimization.
    Solves for position given distances to multiple beacons.
    """
    
    def __init__(self, min_beacons: int = 3, min_distance: float = 0.1):
        """
        Args:
            min_beacons: Minimum number of beacons required for positioning
            min_distance: Minimum valid distance in meters (default: 0.1m)
        """
        self.min_beacons = min_beacons
        self.min_distance = min_distance
        
    def residuals(self, position: np.ndarray, beacon_positions: np.ndarray, 
                  distances: np.ndarray) -> np.ndarray:
        """
        Calculate residuals for least squares optimization.
        
        Args:
            position: Current estimate of tag position [x, y]
            beacon_positions: Array of beacon positions [[x1, y1], [x2, y2], ...]
            distances: Array of measured distances to each beacon
            
        Returns:
            Array of residuals
        """
        calculated_distances = np.sqrt(np.sum((beacon_positions - position) ** 2, axis=1))
        return calculated_distances - distances
    
    def compute_position(self, beacons: Dict[str, Dict], 
                        distances: Dict[str, float]) -> Optional[Tuple[float, float, float]]:
        """
        Compute 2D position using trilateration.
        
        Args:
            beacons: Dictionary of beacon info {beacon_id: {x, y, ...}}
            distances: Dictionary of distances {beacon_id: distance}
            
        Returns:
            Tuple of (x, y, error) or None if insufficient data
        """
        # Filter valid beacons with distance measurements
        valid_beacons = []
        valid_distances = []
        filtered_beacons = []  # Track beacons filtered out
        
        for beacon_id, distance in distances.items():
            if beacon_id not in beacons:
                continue
                
            # Check minimum distance threshold
            if distance < self.min_distance:
                filtered_beacons.append(beacon_id)
                logger.debug(f"Beacon {beacon_id} filtered: distance {distance:.3f}m < {self.min_distance}m")
                continue
            
            if distance > 0:
                beacon = beacons[beacon_id]
                valid_beacons.append([beacon['x'], beacon['y']])
                valid_distances.append(distance)
        
        if filtered_beacons:
            logger.info(f"Filtered {len(filtered_beacons)} beacon(s) due to distance < {self.min_distance}m: {filtered_beacons}")
        
        if len(valid_beacons) < self.min_beacons:
            logger.warning(f"Insufficient beacons or wrong ID: {len(valid_beacons)} < {self.min_beacons}")
            return None
        
        beacon_positions = np.array(valid_beacons)
        distance_array = np.array(valid_distances)
        
        # Initial guess: centroid of beacons
        initial_position = np.mean(beacon_positions, axis=0)
        
        # Solve using least squares
        try:
            result = least_squares(
                self.residuals,
                initial_position,
                args=(beacon_positions, distance_array),
                method='lm'  # Levenberg-Marquardt algorithm
            )
            
            x, y = result.x
            error = np.sqrt(np.mean(result.fun ** 2))  # RMS error
            
            logger.debug(f"Position computed: ({x:.2f}, {y:.2f}), error: {error:.3f}m")
            return (float(x), float(y), float(error))
            
        except Exception as e:
            logger.error(f"Trilateration failed: {e}")
            return None


class KalmanFilter2D:
    """
    Simple 2D Kalman filter for smoothing position estimates.
    """
    
    def __init__(self, process_noise: float = 0.05, measurement_noise: float = 1.0):
        """
        Args:
            process_noise: Process noise covariance
            measurement_noise: Measurement noise covariance
        """
        self.Q = np.eye(2) * process_noise  # Process noise
        self.R = np.eye(2) * measurement_noise  # Measurement noise
        self.P = np.eye(2)  # Estimate covariance
        self.x = None  # State estimate
        
    def update(self, measurement: np.ndarray) -> np.ndarray:
        """
        Update filter with new measurement.
        
        Args:
            measurement: Measured position [x, y]
            
        Returns:
            Filtered position estimate
        """
        if self.x is None:
            # Initialize with first measurement
            self.x = measurement
            return self.x
        
        # Prediction (assuming constant position)
        x_pred = self.x
        P_pred = self.P + self.Q
        
        # Update
        K = P_pred @ np.linalg.inv(P_pred + self.R)  # Kalman gain
        self.x = x_pred + K @ (measurement - x_pred)
        self.P = (np.eye(2) - K) @ P_pred
        
        return self.x


class ToFPositioning:
    """
    Complete ToF/ToA positioning system combining all components.
    """
    
    def __init__(self, min_beacons: int = 3, use_kalman: bool = True,
                 process_noise: float = 0.05, measurement_noise: float = 1.0,
                 min_distance: float = 0.1, max_distance: float = 15.0):
        """
        Args:
            min_beacons: Minimum beacons required
            use_kalman: Whether to use Kalman filtering
            process_noise: Kalman process noise
            measurement_noise: Kalman measurement noise
            min_distance: Minimum valid distance in meters (default: 0.1m)
            max_distance: Maximum valid distance in meters (default: 15.0m)
        """
        self.calibration = RadiusCalibration()
        self.trilateration = Trilateration(min_beacons=min_beacons, min_distance=min_distance)
        self.max_distance = max_distance
        self.use_kalman = use_kalman
        
        if use_kalman:
            self.kalman = KalmanFilter2D(process_noise, measurement_noise)
        else:
            self.kalman = None
            
        self.last_position = None
        
    def compute_position(self, beacons: Dict[str, Dict], 
                        raw_distances: Dict[str, float]) -> Optional[Dict]:
        """
        Compute position from raw distance measurements.
        
        Args:
            beacons: Beacon configurations
            raw_distances: Raw distance measurements
            
        Returns:
            Dictionary with position info or None
        """
        # Apply calibration and filter by max_distance
        calibrated_distances = {}
        for beacon_id, dist in raw_distances.items():
            calibrated_dist = self.calibration.calibrate_distance(beacon_id, dist)
            
            # Filter out distances exceeding max_distance
            if calibrated_dist > self.max_distance:
                logger.debug(f"Beacon {beacon_id} filtered: distance {calibrated_dist:.3f}m > {self.max_distance}m")
                continue
            
            calibrated_distances[beacon_id] = calibrated_dist
        
        # Compute position via trilateration
        result = self.trilateration.compute_position(beacons, calibrated_distances)
        
        if result is None:
            return None
        
        x, y, error = result
        
        # Apply Kalman filtering if enabled
        if self.use_kalman:
            filtered = self.kalman.update(np.array([x, y]))
            x, y = filtered[0], filtered[1]
        
        self.last_position = (x, y)
        
        return {
            'x': x,
            'y': y,
            'error': error,
            'num_beacons': len(calibrated_distances),
            'distances': calibrated_distances
        }
