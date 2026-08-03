import numpy as np
import time
import math

class StepDetection:
    def __init__(self, upper_threshold=1.0, lower_threshold=-1.0, min_time=0.1, max_time=0.6):
        self.upper_threshold = upper_threshold
        self.lower_threshold = lower_threshold
        self.min_time = min_time
        self.max_time = max_time
        self.high_peak_time = None
        
    def detect_step(self, value, current_time):
        if value >= 5 or value <= -5: # Lọc nhiễu văng tay quá mạnh
            self.high_peak_time = None
            return False
            
        if value > self.upper_threshold and self.high_peak_time is None:
            self.high_peak_time = current_time
            return False
        elif value < self.lower_threshold and self.high_peak_time is not None:
            time_diff = current_time - self.high_peak_time
            if self.min_time <= time_diff <= self.max_time:
                self.high_peak_time = None
                return True
            else:
                self.high_peak_time = None
        return False

class PDRKalmanFusion:
    def __init__(self, initial_x=0.0, initial_y=0.0, step_length=0.74):
        self.step_length = step_length
        self.state = np.array([initial_x, initial_y], dtype=float)
        self.P = np.eye(2) * 5.0  # Ma trận hiệp phương sai ban đầu
        
        # Ma trận hệ thống
        self.Q = np.eye(2) * 0.1  # Q (Process Noise) Tăng -> nhạy
        self.R = np.eye(2) * 2.0  # R (Measurement Noise) Nhiễu đo lường : Tăng -> Lì
        
    def predict_pdr(self, yaw_degrees):
        """1: Dự đoán vị trí dựa trên bước chân (PDR)"""
        # Đổi góc sang Radian để tính sin, cos
        yaw_rad = math.radians(yaw_degrees)
        
        # Tính toán độ dời (dx, dy)
        dx = self.step_length * math.sin(yaw_rad)
        dy = self.step_length * math.cos(yaw_rad)
        
        # Cập nhật trạng thái
        self.state[0] += dx
        self.state[1] += dy
        
        # Tăng độ bất định vì di chuyển bằng PDR lâu sẽ tích lũy sai số
        self.P = self.P + self.Q
        
        return self.state[0], self.state[1]
        
    def update_cnn(self, cnn_x, cnn_y):
        """2: Hiệu chỉnh bằng kết quả của CNN"""
        z = np.array([cnn_x, cnn_y], dtype=float)
        
        # Tính toán Kalman Gain
        S = self.P + self.R
        K = self.P @ np.linalg.inv(S)
        
        # Hiệu chỉnh trạng thái
        y = z - self.state
        self.state = self.state + K @ y
        
        # Hiệu chỉnh ma trận hiệp phương sai
        self.P = (np.eye(2) - K) @ self.P
        
        return self.state[0], self.state[1]