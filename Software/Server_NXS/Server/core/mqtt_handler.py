import asyncio
import json
import os
import csv
import time
from collections import deque
import numpy as np

import database_models
import core.globals_var as globals_var
from core.background_tasks import _save_new_device
from positioning import ToFPositioning
from sensor_fusion import StepDetection, PDRKalmanFusion

LOG_DIR = os.path.join(globals_var.ROOT_DIR, 'trajectory_data')
os.makedirs(LOG_DIR, exist_ok=True)
TRAJECTORY_CSV_PATH = os.path.join(LOG_DIR, 'trajectory_log.csv')

def log_trajectory(tag_id, x, y, pos_type):
    file_exists = os.path.exists(TRAJECTORY_CSV_PATH)
    with open(TRAJECTORY_CSV_PATH, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "tag_id", "x", "y", "type"])
        writer.writerow([time.time(), tag_id, x, y, pos_type])

# HÀM ĐƯỢC GỌI KHI CÓ TIN NHẮN MQTT
def handle_incoming_mqtt_data(msg_dict):

    data_type = msg_dict.get("data_type")

    # /-------------------------- XỬ LÝ DỮ LIỆU UWB TỪ THIẾT BỊ ----------------------------/
    if data_type == "user_data_uwb":

        hex_id = msg_dict.get("hex_id")
        bno_data = msg_dict.get("bno", {})
        euler_data = bno_data.get("euler", {})
        valve_data = msg_dict.get("valve", {})
        button_data = msg_dict.get("button", {})
        yaw_val = euler_data.get("yaw", 0.0)
        valve_per_val = valve_data.get("open", 0.0)
        spray_per_val = valve_data.get("mode", 100.0)
        
        # Bắn dữ liệu qua WebSocket
        if hex_id and globals_var.active_websockets:
            for ws in globals_var.active_websockets:
                asyncio.create_task(ws.send_json({
                    "tag_id": hex_id, 
                    "yaw": round(yaw_val, 1), 
                    "valve_per": round(valve_per_val, 1), 
                    "spray_per": round(spray_per_val, 1), 
                    "data_type": "uwb"
                }))
        # Lưu về DB
        new_record = database_models.UserDataUWB(
            accx=bno_data.get("acc", {}).get("x", 0.0),
            accy=bno_data.get("acc", {}).get("y", 0.0),
            accz=bno_data.get("acc", {}).get("z", 0.0),
            magx=bno_data.get("mag", {}).get("x", 0.0),
            magy=bno_data.get("mag", {}).get("y", 0.0),
            magz=bno_data.get("mag", {}).get("z", 0.0),
            gyrox=bno_data.get("gyro", {}).get("x", 0.0),
            gyroy=bno_data.get("gyro", {}).get("y", 0.0),
            gyroz=bno_data.get("gyro", {}).get("z", 0.0),
            pitch=euler_data.get("pitch", 0.0),
            roll=euler_data.get("roll", 0.0),
            yaw=yaw_val,
            valve_open=valve_per_val,
            valve_mode=spray_per_val,
            btn_a=button_data.get("A", 0),
            btn_b=button_data.get("B", 0),
            btn_c=button_data.get("C", 0)
        )
        globals_var.db_buffer_uwb.append(new_record)
        return

    # /------------------------- XỬ LÝ DỮ LIỆU UWB RANGING ----------------------------/
    if data_type == "uwb_ranging":
        beacon_id = msg_dict["beacon_id"]
        measurements = msg_dict["measurements"] 
        
        for tag_id, distance in measurements.items():
            # Lưu UWB Device (Nếu trong DB chưa có)
            if tag_id not in globals_var.KNOWN_UWB_DEVICES:
                globals_var.KNOWN_UWB_DEVICES.add(tag_id)
                asyncio.create_task(asyncio.to_thread(_save_new_device, "UWB", tag_id))
                print(f"[Noti] 🌟 Found new UWB Device: {tag_id}")
                for ws in globals_var.device_manager_websockets:
                    asyncio.create_task(ws.send_json({"type": "new_device"}))
            # Khởi tạo buffer cho Tag này nếu chưa có
            if tag_id not in globals_var.uwb_distance_buffer:
                globals_var.uwb_distance_buffer[tag_id] = {}
                
            globals_var.uwb_distance_buffer[tag_id][beacon_id] = distance

            if not globals_var.active_websockets: continue 
            
            if len(globals_var.uwb_distance_buffer[tag_id]) >= 3:
                if tag_id not in globals_var.uwb_trackers:
                    globals_var.uwb_trackers[tag_id] = ToFPositioning(min_beacons=3, use_kalman=True)
                
                if not globals_var.BEACONS_CONFIG:
                    print("[Warning] ⚠️ No founds UWB locations on RAM")
                    globals_var.uwb_distance_buffer[tag_id].clear()
                    return
                
                cell_length_m = globals_var.CURRENT_UWB_CELL_LENGTH

                # Chuyển tọa độ beacon sang mét
                beacons_in_meters = {}
                for b_id, b_pos in globals_var.BEACONS_CONFIG.items():
                    beacons_in_meters[b_id] = {
                        "x": b_pos["x"] * cell_length_m,
                        "y": b_pos["y"] * cell_length_m
                    }

                result = globals_var.uwb_trackers[tag_id].compute_position(beacons_in_meters, globals_var.uwb_distance_buffer[tag_id])
                
                if result:
                    # Tọa độ tuyệt đối hệ Mét
                    meter_x = result['x']
                    meter_y = result['y']

                    # Tọa độ quy đổi từ Mét -> Grid
                    grid_x = meter_x / cell_length_m
                    grid_y = meter_y / cell_length_m
                    
                    x_val_grid = round(grid_x, 1)
                    y_val_grid = round(grid_y, 1)
                    err_val = result.get('error', result.get('accuracy', 0.0))
                    
                    # Gửi tọa độ theo Grid lên Websocket
                    payload = {
                        "type": "uwb",
                        "tag_id": tag_id, 
                        "x": x_val_grid,
                        "y": y_val_grid,
                        "error": round(err_val, 1)
                    }
                    for ws in globals_var.active_websockets:
                        asyncio.create_task(ws.send_json(payload))

                    # Gửi tọa độ theo mét qua MQTT
                    if globals_var.mqtt_client:
                        topic = f"user_pos/{tag_id}"
                        tag_score = globals_var.CURRENT_SCORES.get(tag_id, 1000)
                        message = json.dumps({
                            "x": float(round(meter_x, 1)),
                            "y": float(round(meter_y, 1)),
                            "score": int(tag_score)
                        })                                                                                                                                                               
                        globals_var.mqtt_client.publish(topic, message)
                        print(f'[MQTT] 👤 Sent User Position message: {message} to topic: {topic}')

                        log_trajectory(tag_id, meter_x, meter_y, "UWB")
                    
                    # Sau khi tính xong, xóa buffer này để tính tiếp    
                    globals_var.uwb_distance_buffer[tag_id].clear()
        return
    # /---------------------------------------------------------------------------------/
    
    # /-------------------------- XỬ LÝ DỮ LIỆU RSSI TRAINING ----------------------------/
    if data_type == "user_data_rssi_training":
        hex_id = msg_dict.get("hex_id")
        rssi_w = msg_dict.get("rssi_wifi", {})
        rssi_b = msg_dict.get("rssi_ble", {})
        mag = msg_dict.get("bno", {}).get("mag", {})
        
        # Làm phẳng dữ liệu cho API Collect Data
        flat_data = {
            "hex_id": hex_id,
            "rssi_wifi_1": rssi_w.get("1", 0.0), "rssi_wifi_2": rssi_w.get("2", 0.0),
            "rssi_wifi_3": rssi_w.get("3", 0.0), "rssi_wifi_4": rssi_w.get("4", 0.0),
            "rssi_ble_1": rssi_b.get("1", 0.0),  "rssi_ble_2": rssi_b.get("2", 0.0),
            "rssi_ble_3": rssi_b.get("3", 0.0),  "rssi_ble_4": rssi_b.get("4", 0.0),
            "magnetic_field_y": mag.get("y", 0.0),
            "magnetic_field_z": mag.get("z", 0.0)
        }
        
        if globals_var.data_queue is not None:
            if globals_var.data_queue.full():
                try:
                    globals_var.data_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            globals_var.data_queue.put_nowait(flat_data)
        return

    # /-------------------------- XỬ LÝ DỮ LIỆU RSSI REALITY (DÀNH CHO HUẤN LUYỆN THỰC TẾ) ----------------------------/
    if data_type == "user_data_rssi_reality":
        hex_id = msg_dict.get("hex_id")
        
        bno_data = msg_dict.get("bno", {})
        euler_data = bno_data.get("euler", {})
        valve_data = msg_dict.get("valve", {})
        button_data = msg_dict.get("button", {})
        rssi_w = msg_dict.get("rssi_wifi", {})
        rssi_b = msg_dict.get("rssi_ble", {})
        
        yaw_val = euler_data.get("yaw", 0.0)
        valve_per_val = valve_data.get("open", 0.0)
        spray_per_val = valve_data.get("mode", 100.0)

        # Gửi thông số qua WebSocket
        if hex_id and globals_var.active_websockets:
            for ws in globals_var.active_websockets:
                asyncio.create_task(ws.send_json({
                    "tag_id": hex_id, 
                    "yaw": round(yaw_val, 1), 
                    "valve_per": round(valve_per_val, 1), 
                    "spray_per": round(spray_per_val, 1), 
                    "data_type": "rssi"
                }))

        # Lưu RSSI Device (Nếu trong DB chưa có)
        if hex_id and hex_id not in globals_var.KNOWN_RSSI_DEVICES:
            globals_var.KNOWN_RSSI_DEVICES.add(hex_id)
            asyncio.create_task(asyncio.to_thread(_save_new_device, "RSSI", hex_id))
            print(f"[Noti] 🌟 Found new RSSI Device: {hex_id}")
            for ws in globals_var.device_manager_websockets:
                asyncio.create_task(ws.send_json({"type": "new_device"}))
                
        # Lưu toàn bộ chi tiết quá trình huấn luyện vào DB
        new_record = database_models.UserDataRSSI(
            rssi_wifi_1=rssi_w.get("1", 0.0), rssi_wifi_2=rssi_w.get("2", 0.0),
            rssi_wifi_3=rssi_w.get("3", 0.0), rssi_wifi_4=rssi_w.get("4", 0.0),
            rssi_ble_1=rssi_b.get("1", 0.0), rssi_ble_2=rssi_b.get("2", 0.0),
            rssi_ble_3=rssi_b.get("3", 0.0), rssi_ble_4=rssi_b.get("4", 0.0),
            accx=bno_data.get("acc", {}).get("x", 0.0), accy=bno_data.get("acc", {}).get("y", 0.0), accz=bno_data.get("acc", {}).get("z", 0.0),
            magx=bno_data.get("mag", {}).get("x", 0.0), magy=bno_data.get("mag", {}).get("y", 0.0), magz=bno_data.get("mag", {}).get("z", 0.0),
            gyrox=bno_data.get("gyro", {}).get("x", 0.0), gyroy=bno_data.get("gyro", {}).get("y", 0.0), gyroz=bno_data.get("gyro", {}).get("z", 0.0),
            pitch=euler_data.get("pitch", 0.0), roll=euler_data.get("roll", 0.0), yaw=yaw_val,
            valve_open=valve_per_val, valve_mode=spray_per_val,
            btn_a=button_data.get("A", 0), btn_b=button_data.get("B", 0), btn_c=button_data.get("C", 0)
        )
        globals_var.db_buffer_rssi.append(new_record)

        # Dự đoán vị trí kết hợp PDR và CNN
        if not globals_var.active_websockets or globals_var.ai_predictor is None or globals_var.ai_predictor.model is None:
            return  

        current_time = time.time()

        # 1. Khởi tạo các tracker cho thiết bị mới nếu chưa có
        if hex_id not in globals_var.rssi_buffers:
            globals_var.rssi_buffers[hex_id] = deque(maxlen=10)
        if hex_id not in globals_var.step_detectors:
            globals_var.step_detectors[hex_id] = StepDetection()
        if hex_id not in globals_var.pdr_fusion_trackers:
            globals_var.pdr_fusion_trackers[hex_id] = PDRKalmanFusion(initial_x=0.0, initial_y=0.0)

        # 2. XỬ LÝ PDR (Mỗi khi có bản tin IMU đến)
        # Tính góc di chuyển thực tế (Yaw + North Offset)
        real_heading = (yaw_val + globals_var.CURRENT_MAP_NORTH_OFFSET) % 360
        acc_z = bno_data.get("acc", {}).get("z", 0.0)
        
        is_step = globals_var.step_detectors[hex_id].detect_step(acc_z, current_time)
        
        if is_step:
            # Nếu có bước chân -> PDR thực hiện Predict tịnh tiến vị trí
            pdr_x, pdr_y = globals_var.pdr_fusion_trackers[hex_id].predict_pdr(real_heading)

        # 3. XỬ LÝ CNN (Gom đủ 10 mẫu RSSI mới dự đoán 1 lần)
        features = [
            rssi_w.get("1", 0.0), rssi_w.get("2", 0.0), rssi_w.get("3", 0.0), rssi_w.get("4", 0.0),
            rssi_b.get("1", 0.0), rssi_b.get("2", 0.0), rssi_b.get("3", 0.0), rssi_b.get("4", 0.0),
            bno_data.get("mag", {}).get("y", 0.0), bno_data.get("mag", {}).get("z", 0.0)
        ]
        globals_var.rssi_buffers[hex_id].append(features)

        if len(globals_var.rssi_buffers[hex_id]) == 10:
            window_data = np.array(globals_var.rssi_buffers[hex_id]).reshape(1, -1)
            try:
                # CNN Dự đoán tọa độ
                raw_x, raw_y, accuracy = globals_var.ai_predictor.predict_realtime(window_data)
                
                # SENSOR FUSION
                final_x, final_y = globals_var.pdr_fusion_trackers[hex_id].update_cnn(raw_x, raw_y)
                
                # Reset buffer để gom 10 mẫu tiếp theo
                globals_var.rssi_buffers[hex_id].clear()
                
                # Gửi lên WebSocket
                payload = {
                    "type": "rssi",
                    "tag_id": hex_id,
                    "x": round(final_x, 1),
                    "y": round(final_y, 1),
                    "accuracy": round(accuracy * 100, 1)
                }
                for ws in globals_var.active_websockets:
                    asyncio.create_task(ws.send_json(payload))

                # Đóng gói JSON gửi MQTT cho thiết bị
                if globals_var.mqtt_client:
                    topic = f"user_pos/{hex_id}"
                    tag_score = globals_var.CURRENT_SCORES.get(hex_id, 1000)
                    message = json.dumps({
                        "x": float(round(final_x, 1)),
                        "y": float(round(final_y, 1)),
                        "score": int(tag_score)
                    })
                    globals_var.mqtt_client.publish(topic, message)
                    print(f'[MQTT] 👤 Sent User Position message: {message} to topic: {topic}')

                    log_trajectory(hex_id, final_x, final_y, "RSSI")
                    
            except Exception as e:
                print(f"[Err] ❌ Real-time prediction error: {e}")
    # /---------------------------------------------------------------------------------/

