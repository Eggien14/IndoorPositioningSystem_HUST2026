import numpy as np
import pandas as pd
import os
import core.globals_var as globals_var

class WBOFilter:
    def __init__(self, min_value, max_value, a_factor=10, b_factor=3, threshold=0):
        if min_value == max_value:
            self.min_value = min_value - 1
            self.max_value = max_value + 1
            self.weights = np.ones(max_value - min_value + 3) * 1/(max_value - min_value + 3)
        else:
            self.min_value = min_value
            self.max_value = max_value
            self.weights = np.ones(max_value - min_value + 1) * 1/(max_value - min_value + 1)
        self.a_factor = a_factor
        self.b_factor = b_factor
        self.threshold = threshold
        
    def get_correlation_point(self):
        lower_margin = None
        upper_margin = None
        for i in range(len(self.weights)):
            if lower_margin is None and self.weights[i] > self.threshold:
                lower_margin = i
            if upper_margin is None and self.weights[-i] > self.threshold:
                upper_margin = len(self.weights) - (i + 1)
        return (upper_margin - lower_margin) / 2 + lower_margin
    
    def get_filter_value(self):
        min_weight = np.min(self.weights)
        adjusted_weights = self.weights - min_weight
        sum_of_weights = np.sum(adjusted_weights)
        values = np.arange(self.min_value, self.max_value + 1)
        sum_of_weighted_values = np.dot(adjusted_weights, values)
        return (sum_of_weighted_values / sum_of_weights)
    
    def proposed_filter(self, rssi):
        x = rssi - self.min_value
        correlation_point = self.get_correlation_point()

        new_weight = np.tanh(self.weights[x] + self.a_factor / (abs(x - correlation_point) + 1e-6))
        previous_weight = self.weights[x]
        self.weights[x] = new_weight

        for i in range(len(self.weights)):
            if i != x:
                self.weights[i] = np.tanh(self.weights[i] - self.b_factor * 
                abs(new_weight - previous_weight) / (self.max_value - self.min_value + 1))
        return self.get_filter_value()

class Preprocessor:
    def __init__(self, data_df, time_steps=10, map_id=1):
        self.data = data_df
        self.time_steps = time_steps
        self.map_id = map_id
        
        self.rssi_cols = [
            'rssi_wifi_1', 'rssi_wifi_2', 'rssi_wifi_3', 'rssi_wifi_4',
            'rssi_ble_1', 'rssi_ble_2', 'rssi_ble_3', 'rssi_ble_4'
        ]
        self.mag_cols = ['magnetic_field_y', 'magnetic_field_z']
        self.all_cols = self.rssi_cols + self.mag_cols
        
    def preprocess(self):
            # Mảng chứa dữ liệu ĐÃ QUA LỌC (WBO)
            final_filtered_rows = []
            # Mảng chứa dữ liệu THÔ (Raw - Chỉ trượt cửa sổ, không lọc)
            final_raw_rows = []
            
            # Nhóm dữ liệu theo từng điểm thu thập (coord_x, coord_y)
            grouped = self.data.groupby(['coord_x', 'coord_y'])
            

            for (x, y), group in grouped:
                filtered_group = {}
                raw_group = {}
                
                # Xử lý lọc WBO (Giữ nguyên)
                for col in self.rssi_cols:
                    col_data = group[col].values
                    raw_group[col] = col_data 
                    min_val, max_val = int(round(np.min(col_data))), int(round(np.max(col_data)))
                    if min_val == max_val: 
                        filtered_group[col] = col_data
                    else:
                        wbo = WBOFilter(min_val, max_val)
                        filtered_group[col] = [wbo.proposed_filter(int(round(val))) for val in col_data]
                
                for col in self.mag_cols:
                    filtered_group[col] = group[col].values
                    raw_group[col] = group[col].values
                    
                temp_filtered_df = pd.DataFrame(filtered_group)
                temp_raw_df = pd.DataFrame(raw_group)
                
                filtered_matrix = temp_filtered_df[self.all_cols].values 
                raw_matrix = temp_raw_df[self.all_cols].values
                
                label = f"{x}_{y}"

                # ---> BƯỚC MỚI: CHIA TRAIN/TEST TRƯỚC KHI CẮT WINDOW <---
                split_idx = int(len(filtered_matrix) * 0.8) # Lấy mốc 80%

                train_filtered = filtered_matrix[:split_idx]
                test_filtered = filtered_matrix[split_idx:]
                train_raw = raw_matrix[:split_idx]
                test_raw = raw_matrix[split_idx:]
                
                # 1. Cắt cửa sổ cho tập TRAIN (Gắn nhãn 'train' ở cuối)
                for i in range(len(train_filtered) - self.time_steps + 1):
                    window_filtered = train_filtered[i : i + self.time_steps]
                    window_raw = train_raw[i : i + self.time_steps]
                    final_filtered_rows.append(list(window_filtered.flatten()) + [label, "train"])
                    final_raw_rows.append(list(window_raw.flatten()) + [label, "train"])

                # 2. Cắt cửa sổ cho tập TEST (Gắn nhãn 'test' ở cuối)
                for i in range(len(test_filtered) - self.time_steps + 1):
                    window_filtered = test_filtered[i : i + self.time_steps]
                    window_raw = test_raw[i : i + self.time_steps]
                    final_filtered_rows.append(list(window_filtered.flatten()) + [label, "test"])
                    final_raw_rows.append(list(window_raw.flatten()) + [label, "test"])

            # ---> BƯỚC MỚI: Cập nhật tên cột, có thêm cột "split" <---
            col_names = [str(i) for i in range(len(self.all_cols) * self.time_steps)] + ["label", "split"]
            
            final_filtered_df = pd.DataFrame(final_filtered_rows, columns=col_names)

            # 4. Xuất ra file CSV
            col_names = [str(i) for i in range(len(self.all_cols) * self.time_steps)] + ["label", "split"]
            
            final_filtered_df = pd.DataFrame(final_filtered_rows, columns=col_names)
            final_raw_df = pd.DataFrame(final_raw_rows, columns=col_names)

            os.makedirs(os.path.join(globals_var.ROOT_DIR, 'rssi_data'), exist_ok=True)
            
            # ---> SỬA TÊN FILE Ở ĐÂY: Nối chuỗi map_id vào đuôi tên file <---
            filtered_file_path = os.path.join(globals_var.ROOT_DIR, 'rssi_data', f'rssi_preprocess_map_{self.map_id}.csv') 
            final_filtered_df.to_csv(filtered_file_path, index=False)
            
            raw_file_path = os.path.join(globals_var.ROOT_DIR, 'rssi_data', f'rssi_preprocess_raw_map_{self.map_id}.csv') 
            final_raw_df.to_csv(raw_file_path, index=False)
            
            return filtered_file_path, raw_file_path