import os, traceback
import json
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, text
import subprocess

import database_models
import core.globals_var as globals_var
from api.dependency import get_db
from models import (
    RSSIMapInfoSchema, CollectDataRequestSchema, UwbMapInfoSchema, 
    UserSchema, DeviceRenameSchema, ScenarioSchema, TrainingHistorySchema
)
from wbo_filter import Preprocessor
from ml_model import MLModel
from plot.plot_rssi import plot_before_after_rssi

router = APIRouter()

# /----------------------------- API ENDPOINTS -------------------------------------/

# =====================================================================
# API ĐĂNG KÝ VÀ ĐĂNG NHẬP TÀI KHOẢN
# =====================================================================
@router.post("/register")
def register(user: UserSchema, db: Session = Depends(get_db)):
    existing_user = db.query(database_models.User).filter(database_models.User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    new_user = database_models.User(username=user.username, password=user.password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User registered successfully"}

@router.post("/login")
def login(user: UserSchema, db: Session = Depends(get_db)):
    db_user = db.query(database_models.User).filter(
        database_models.User.username == user.username,
        database_models.User.password == user.password
    ).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {
        "message": "Login successful",
        "user_id": db_user.id,
        "username": db_user.username
    }
# =====================================================================
# API QUẢN LÝ THIẾT BỊ 
# =====================================================================
@router.get("/devices/fingerprint")
def get_rssi_devices(db: Session = Depends(get_db)):
    return db.query(database_models.DeviceRSSI).all()

@router.put("/devices/fingerprint/{device_id}")
def rename_rssi_device(device_id: int, payload: DeviceRenameSchema, db: Session = Depends(get_db)):
    dev = db.query(database_models.DeviceRSSI).filter_by(device_id=device_id).first()
    if not dev: raise HTTPException(status_code=404)
    dev.device_name = payload.device_name
    db.commit()
    return dev

@router.delete("/devices/fingerprint/{device_id}")
def delete_rssi_device(device_id: int, db: Session = Depends(get_db)):
    dev = db.query(database_models.DeviceRSSI).filter_by(device_id=device_id).first()
    if not dev: 
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Xóa khỏi Cache RAM
    if dev.device_hex_id in globals_var.KNOWN_RSSI_DEVICES:
        globals_var.KNOWN_RSSI_DEVICES.remove(dev.device_hex_id)
        
    db.delete(dev)
    db.commit()
    if db.query(database_models.DeviceRSSI).count() == 0:
        db.execute(text("ALTER TABLE device_rssi AUTO_INCREMENT = 1"))
        db.commit()

    return {"message": "RSSI device deleted successfully"}

@router.get("/devices/uwb")
def get_uwb_devices(db: Session = Depends(get_db)):
    return db.query(database_models.DeviceUWB).all()

@router.put("/devices/uwb/{device_id}")
def rename_uwb_device(device_id: int, payload: DeviceRenameSchema, db: Session = Depends(get_db)):
    dev = db.query(database_models.DeviceUWB).filter_by(device_id=device_id).first()
    if not dev: raise HTTPException(status_code=404)
    dev.device_name = payload.device_name
    db.commit()
    return dev

@router.delete("/devices/uwb/{device_id}")
def delete_uwb_device(device_id: int, db: Session = Depends(get_db)):
    dev = db.query(database_models.DeviceUWB).filter_by(device_id=device_id).first()
    if not dev: 
        raise HTTPException(status_code=404, detail="Device not found")
        
    # Xóa khỏi Cache RAM
    if dev.device_hex_id in globals_var.KNOWN_UWB_DEVICES:
        globals_var.KNOWN_UWB_DEVICES.remove(dev.device_hex_id)
        
    db.delete(dev)
    db.commit()
    if db.query(database_models.DeviceUWB).count() == 0:
        db.execute(text("ALTER TABLE device_uwb AUTO_INCREMENT = 1"))
        db.commit()
    return {"message": "UWB device deleted successfully"}
# =====================================================================
# API QUẢN LÝ MAP RSSI
# =====================================================================
@router.get("/rssi_maps")
def get_all_maps(db: Session = Depends(get_db)):
    db_maps = db.query(database_models.RSSIMapInfo).all()
    return db_maps

@router.post("/rssi_maps")
def create_map(map_info: RSSIMapInfoSchema, db: Session = Depends(get_db)):
    db_map = database_models.RSSIMapInfo(**map_info.model_dump())
    db.add(db_map)
    db.commit()
    db.refresh(db_map)
    return db_map

@router.get("/rssi_maps/{id}")
def get_map_by_id(id: int, db: Session = Depends(get_db)):
    db_map = db.query(database_models.RSSIMapInfo).filter(database_models.RSSIMapInfo.map_info_id == id).first()
    if not db_map:
        raise HTTPException(status_code=404, detail="Map not found")
    return db_map

@router.put("/rssi_maps/{id}")
def update_map(id: int, map_info: RSSIMapInfoSchema, db: Session = Depends(get_db)):
    db_map = db.query(database_models.RSSIMapInfo).filter(database_models.RSSIMapInfo.map_info_id == id).first()
    if not db_map:
        raise HTTPException(status_code=404, detail="Map not found")
    else:
        db_map.total_units = map_info.total_units
        db_map.area_of_one_unit = map_info.area_of_one_unit
        db_map.walkable_area = map_info.walkable_area    
        db_map.north_offset = map_info.north_offset
        db_map.router_location = map_info.router_location
        db_map.router_number = map_info.router_number
        db_map.cols = map_info.cols
        db_map.rows = map_info.rows
        db_map.blocked_cells = map_info.blocked_cells
    db.commit()
    db.refresh(db_map)
    return db_map

@router.delete("/rssi_maps/{id}")
def delete_map(id: int, db: Session = Depends(get_db)):
    db_map = db.query(database_models.RSSIMapInfo).filter(database_models.RSSIMapInfo.map_info_id == id).first()
    if not db_map:
        raise HTTPException(status_code=404, detail="Map not found")

    db.delete(db_map)
    db.commit()

    if db.query(database_models.RSSIMapInfo).count() == 0:
        db.execute(text("ALTER TABLE rssi_map_info AUTO_INCREMENT = 1"))
        db.commit()

    return {"status": "deleted"}
# =====================================================================
# API CHỌN MAP ĐỂ LOAD MODEL AI VÀ GỬI THÔNG TIN MAP XUỐNG DEVICE QUA MQTT
# =====================================================================
@router.post("/set_active_rssi_map/{id}")
def set_active_rssi_map(id: int, db: Session = Depends(get_db)):
    
    db_map = db.query(database_models.RSSIMapInfo).filter(database_models.RSSIMapInfo.map_info_id == id).first()
    if not db_map:
        raise HTTPException(status_code=404, detail="Map not found")
        
    try:
        print(f"[Noti] 🔄 Switching AI Model path to Map ID: {id}...")

        globals_var.rssi_buffers.clear()
        globals_var.pdr_fusion_trackers.clear()
        globals_var.step_detectors.clear() 
        if hasattr(globals_var, 'kalman_filters'):
            globals_var.kalman_filters.clear()
        
        # Load model mới
        globals_var.ai_predictor = MLModel(csv_path="", map_id=id)
        globals_var.ai_predictor.load_saved_model()

        # Gửi Map xuống Device
        if globals_var.mqtt_client:
            MAX_COLS = 10
            MAX_ROWS = 10
            offset = db_map.north_offset if db_map.north_offset else 0
            globals_var.CURRENT_MAP_NORTH_OFFSET = float(offset)
            blocked_ids_set = set()

            map_cols = db_map.cols if db_map.cols else MAX_COLS
            map_rows = db_map.rows if db_map.rows else MAX_ROWS

            # Danh sách các ô bị block
            if db_map.blocked_cells:
                for cell in db_map.blocked_cells:
                    try:
                        x_str, y_str = cell.split(':')
                        x_idx = int(float(x_str))
                        y_idx = int(float(y_str))
                        cell_id = y_idx * MAX_COLS + x_idx + 1
                        blocked_ids_set.add(cell_id)
                    except Exception:
                        pass
            # Tính kích thước map
            cell_length_m = (db_map.area_of_one_unit or 1.0) ** 0.5
            map_width_m = int(map_cols * cell_length_m)
            map_height_m = int(map_rows * cell_length_m)

            # Vòng lặp tạo danh sách tọa độ các ô đi được
            walkable_cells = []
            for y in range(map_rows):
                for x in range(map_cols):
                    cell_id = y * MAX_COLS + x + 1
                    
                    if cell_id not in blocked_ids_set:
                        walkable_cells.append([x, y])
            
            payload_dict = {
                "info": {
                    "x": map_width_m,
                    "y": map_height_m,
                    "north_offset": float(offset)
                },
                "cells": walkable_cells
            }
            
            payload = json.dumps(payload_dict)
            globals_var.mqtt_client.publish("map_data/14", payload)
            print(f"[MQTT] 🗺️  Sent RSSI Map Data message: {payload}")
        
        return {"message": f"Successfully loaded AI Model for Map {id}"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"AI Model for Map {id} not found. Please train it first!")
# =====================================================================
# API THU THẬP DỮ LIỆU CHO FINGERPRINTING
# =====================================================================
@router.post("/collect_data")
async def collect_data(request: CollectDataRequestSchema, db: Session = Depends(get_db)):

    # Xóa data cũ trong DB của ô đó để tránh trùng
    db.query(database_models.RSSIForTraining).filter(
        database_models.RSSIForTraining.map_info_id == request.map_info_id,
        database_models.RSSIForTraining.coord_x == request.coord_x,
        database_models.RSSIForTraining.coord_y == request.coord_y).delete(synchronize_session=False)
    db.commit()

    # Xóa data cũ trong queue để tránh trùng lặp khi thu thập dữ liệu mới
    while not globals_var.data_queue.empty():
        try:
            globals_var.data_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

    collected = 0
    while collected < request.samples:
            try:
                msg_dict = await asyncio.wait_for(globals_var.data_queue.get(), timeout=10.0) # Chờ lấy data từ MQTT max 10s

                new_record = database_models.RSSIForTraining(
                    map_info_id=request.map_info_id,
                    coord_x=request.coord_x,
                    coord_y=request.coord_y,
                    rssi_wifi_1=msg_dict["rssi_wifi_1"],
                    rssi_wifi_2=msg_dict["rssi_wifi_2"],
                    rssi_wifi_3=msg_dict["rssi_wifi_3"],
                    rssi_wifi_4=msg_dict["rssi_wifi_4"],
                    rssi_ble_1=msg_dict["rssi_ble_1"],
                    rssi_ble_2=msg_dict["rssi_ble_2"],
                    rssi_ble_3=msg_dict["rssi_ble_3"],
                    rssi_ble_4=msg_dict["rssi_ble_4"],
                    magnetic_field_y=msg_dict["magnetic_field_y"],
                    magnetic_field_z=msg_dict["magnetic_field_z"]
                )
                db.add(new_record)
                collected += 1

                if globals_var.active_websockets:
                    payload = {
                        "type": "collect_progress",
                        "collected": collected,
                        "total": request.samples
                    }
                    for ws in globals_var.active_websockets:
                        asyncio.create_task(ws.send_json(payload))

            except asyncio.TimeoutError:
                print("[Noti] ❌ Device stopped sending data.")
                break

    db.commit()
    return {"message": f"Successfully collected {collected}/{request.samples} samples."}
# =====================================================================
# API TIỀN XỬ LÝ DATA TRƯỚC KHI TRAIN MODEL
# =====================================================================
@router.post("/preprocess_map/{map_info_id}")
def preprocess_map_data(map_info_id: int, db: Session = Depends(get_db)):
    # Lấy dữ liệu từ DB của đúng Map đó
    records = db.query(database_models.RSSIForTraining).filter(
        database_models.RSSIForTraining.map_info_id == map_info_id
    ).all()

    if not records:
        raise HTTPException(status_code=404, detail="No data found for this map.")

    # Chuyển đổi Object sang Pandas DataFrame
    data_dicts = []
    for r in records:
        data_dicts.append({
            'coord_x': r.coord_x,
            'coord_y': r.coord_y,
            'rssi_wifi_1': r.rssi_wifi_1, 'rssi_wifi_2': r.rssi_wifi_2,
            'rssi_wifi_3': r.rssi_wifi_3, 'rssi_wifi_4': r.rssi_wifi_4,
            'rssi_ble_1': r.rssi_ble_1, 'rssi_ble_2': r.rssi_ble_2,
            'rssi_ble_3': r.rssi_ble_3, 'rssi_ble_4': r.rssi_ble_4,
            'magnetic_field_y': r.magnetic_field_y, 'magnetic_field_z': r.magnetic_field_z
        })
    df_raw = pd.DataFrame(data_dicts)

    # Đưa vào bộ lọc WBO
    processor = Preprocessor(data_df=df_raw, map_id=map_info_id)
    filtered_path, raw_path = processor.preprocess()

    try:
        df_filtered = pd.read_csv(filtered_path)

        plot_before_after_rssi(df_raw, df_filtered, output_dir="graphs")
    except Exception as e:
        print(f"⚠️ Error plotting graphs: {e}")

    return {
        "message": "Data filtered successfully!", 
        "filtered_file": filtered_path,
        "raw_file": raw_path
    }
# =====================================================================
# API TRAIN MODEL AI CHO MAP ĐÃ CHỌN
# =====================================================================
@router.post("/train_model/{map_info_id}")
async def train_model(map_info_id: int):
    try:
        csv_file_path = os.path.join(globals_var.ROOT_DIR, 'rssi_data', f'rssi_preprocess_map_{map_info_id}.csv')
        cnn_model = MLModel(csv_path=csv_file_path, map_id=map_info_id) 
        cnn_model.train_model()
        
        return {
            "status": "success",
            "message": f"Trained successfully for Map {map_info_id}!"
        }
    except Exception as e:
        print(f"[Err] ❌ Training Error: {e}")
        raise HTTPException(status_code=500, detail=f"Model training failed: {str(e)}")
# =====================================================================
# API QUẢN LÝ MAP UWB
# =====================================================================
@router.get("/uwb_maps")
def get_all_uwb_maps(db: Session = Depends(get_db)):
    db_maps = db.query(database_models.UwbMapInfo).all()
    return db_maps

@router.post("/uwb_maps")
def create_uwb_map(map_info: UwbMapInfoSchema, db: Session = Depends(get_db)):
    db_map = database_models.UwbMapInfo(**map_info.model_dump())
    db.add(db_map)
    db.commit()
    db.refresh(db_map)
    return db_map

@router.get("/uwb_maps/{id}")
def get_uwb_map_by_id(id: int, db: Session = Depends(get_db)):
    db_map = db.query(database_models.UwbMapInfo).filter(database_models.UwbMapInfo.map_info_id == id).first()
    if not db_map:
        raise HTTPException(status_code=404, detail="Map not found")
    return db_map

@router.put("/uwb_maps/{id}")
def update_uwb_map(id: int, map_info: UwbMapInfoSchema, db: Session = Depends(get_db)):
    db_map = db.query(database_models.UwbMapInfo).filter(database_models.UwbMapInfo.map_info_id == id).first()
    if not db_map:
        raise HTTPException(status_code=404, detail="Map not found")
    else:
        db_map.total_units = map_info.total_units
        db_map.area_of_one_unit = map_info.area_of_one_unit
        db_map.walkable_area = map_info.walkable_area    
        db_map.north_offset = map_info.north_offset
        db_map.beacon_number = map_info.beacon_number
        db_map.beacon_location = map_info.beacon_location
        db_map.cols = map_info.cols
        db_map.rows = map_info.rows
        db_map.blocked_cells = map_info.blocked_cells
    db.commit()
    db.refresh(db_map)

    return db_map

@router.delete("/uwb_maps/{id}")
def delete_uwb_map(id: int, db: Session = Depends(get_db)):
    db_map = db.query(database_models.UwbMapInfo).filter(database_models.UwbMapInfo.map_info_id == id).first()
    if not db_map:
        raise HTTPException(status_code=404, detail="Map not found")

    db.delete(db_map)
    db.commit()

    if db.query(database_models.UwbMapInfo).count() == 0:
        db.execute(text("ALTER TABLE uwb_map_info AUTO_INCREMENT = 1"))
        db.commit()

    return {"status": "deleted"}
# =====================================================================
# API CHỌN MAP UWB ĐỂ GỬI THÔNG TIN MAP (North Offset, Ô bị cản) XUỐNG DEVICE QUA MQTT
# =====================================================================
@router.post("/set_active_uwb_map/{id}")
def set_active_uwb_map(id: int, db: Session = Depends(get_db)):

    db_map = db.query(database_models.UwbMapInfo).filter(database_models.UwbMapInfo.map_info_id == id).first()
    
    if not db_map:
        raise HTTPException(status_code=404, detail="Map not found")
        
    if db_map.beacon_location:
        globals_var.BEACONS_CONFIG = db_map.beacon_location
        globals_var.CURRENT_UWB_CELL_LENGTH = (db_map.area_of_one_unit or 1.0) ** 0.5
    else:
        globals_var.BEACONS_CONFIG = {}
    
    # Gửi Map xuống Device
    if globals_var.mqtt_client:
        MAX_COLS = 10
        MAX_ROWS = 10
        offset = db_map.north_offset if db_map.north_offset else 0
        blocked_ids_set = set()

        map_cols = db_map.cols if db_map.cols else MAX_COLS
        map_rows = db_map.rows if db_map.rows else MAX_ROWS

        # Danh sách các ô bị block
        if db_map.blocked_cells:
            for cell in db_map.blocked_cells:
                try:
                    x_str, y_str = cell.split(':')
                    x_idx = int(float(x_str))
                    y_idx = int(float(y_str))
                    cell_id = y_idx * MAX_COLS + x_idx + 1
                    blocked_ids_set.add(cell_id)
                except Exception:
                    pass
        # Tính kích thước map
        cell_length_m = (db_map.area_of_one_unit or 1.0) ** 0.5
        map_width_m = int(map_cols * cell_length_m)
        map_height_m = int(map_rows * cell_length_m)

        # Vòng lặp tạo danh sách tọa độ các ô đi được
        walkable_cells = []
        for y in range(map_rows):
            for x in range(map_cols):
                cell_id = y * MAX_COLS + x + 1
                
                if cell_id not in blocked_ids_set:
                    walkable_cells.append([x, y])
        
        payload_dict = {
            "info": {
                "x": map_width_m,
                "y": map_height_m,
                "north_offset": float(offset)
            },
            "cells": walkable_cells
        }
        
        payload = json.dumps(payload_dict)
        globals_var.mqtt_client.publish("map_data", payload)
        print(f"[MQTT] 🗺️  Sent UWB Map Data message: {payload}")
        
    return {"message": f"Switched uwb map to ID {id}", "active_beacons": globals_var.BEACONS_CONFIG}
# =====================================================================
# API QUẢN LÝ KỊCH BẢN HUẤN LUYỆN (SCENARIOS & FIRES)
# =====================================================================
@router.post("/scenarios")
def create_scenario(payload: ScenarioSchema, db: Session = Depends(get_db)):

    # Tạo kịch bản mới
    new_scenario = database_models.Scenario(
        map_info_id=payload.map_info_id,
        map_type=payload.map_type,
        scenario_name=payload.scenario_name
    )
    db.add(new_scenario)
    db.commit()
    db.refresh(new_scenario)

    # Tạo danh sách ngọn lửa
    for fire in payload.fires:
        new_fire = database_models.ScenarioFire(
            scenario_id=new_scenario.scenario_id,
            coord_x=fire.coord_x,
            coord_y=fire.coord_y,
            level=fire.level,
            delay_time=fire.delay_time,
            is_spreading=fire.is_spreading
        )
        db.add(new_fire)
    
    db.commit()
    return {"message": "Scenario created successfully", "scenario_id": new_scenario.scenario_id}

@router.get("/scenarios/{map_type}/{map_id}")
def get_scenarios(map_type: str, map_id: int, db: Session = Depends(get_db)):
    # Lấy kịch bản kèm theo toàn bộ ngọn lửa
    scenarios = db.query(database_models.Scenario).filter(
        database_models.Scenario.map_type == map_type,
        database_models.Scenario.map_info_id == map_id
    ).all()
    
    result = []
    for sc in scenarios:
        result.append({
            "scenario_id": sc.scenario_id,
            "scenario_name": sc.scenario_name,
            "fires": [
                {
                    "fire_id": f.fire_id,
                    "coord_x": f.coord_x,
                    "coord_y": f.coord_y,
                    "level": f.level,
                    "delay_time": f.delay_time,
                    "is_spreading": f.is_spreading
                } for f in sc.fires
            ]
        })
    return result

@router.delete("/scenarios/{scenario_id}")
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)):
    sc = db.query(database_models.Scenario).filter_by(scenario_id=scenario_id).first()
    if not sc:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    db.delete(sc)
    db.commit()

    if db.query(database_models.Scenario).count() == 0:
        db.execute(text("ALTER TABLE scenarios AUTO_INCREMENT = 1"))
        db.execute(text("ALTER TABLE scenario_fires AUTO_INCREMENT = 1"))
        db.commit()

    return {"message": "Scenario deleted successfully"}

# =====================================================================
# API QUẢN LÝ LỊCH SỬ HUẤN LUYỆN (TRAINING HISTORY)
# =====================================================================
@router.post("/training_history")
def save_training_history(payload: TrainingHistorySchema, db: Session = Depends(get_db)):
    end_t = datetime.now()
    start_t = end_t - timedelta(seconds=payload.time_elapsed)
    history = database_models.TrainingHistory(
        trainee_name=payload.trainee_name,
        scenario_id=payload.scenario_id,
        device_hex_id=payload.device_hex_id,
        time_elapsed=payload.time_elapsed,   
        start_time=start_t,
        end_time=end_t,
        score=payload.score
    )
    db.add(history)
    db.commit()
    return {"message": "Training session saved successfully!"}

@router.get("/training_history")
def get_training_history(db: Session = Depends(get_db)):
    records = db.query(
        database_models.TrainingHistory.history_id,
        database_models.TrainingHistory.trainee_name,
        database_models.TrainingHistory.scenario_id,
        database_models.TrainingHistory.device_hex_id,
        database_models.TrainingHistory.score,
        database_models.TrainingHistory.start_time,
        database_models.TrainingHistory.end_time,
        database_models.TrainingHistory.time_elapsed,
        database_models.Scenario.scenario_name
        ).join(database_models.Scenario).order_by( 
        desc(database_models.TrainingHistory.start_time)
    ).all()

    return [
        {
            "history_id": r.history_id,
            "trainee_name": r.trainee_name,
            "scenario_id": r.scenario_id,
            "scenario_name": r.scenario_name,
            "device_hex_id": r.device_hex_id,
            "score": r.score,
            "start_time": r.start_time,
            "end_time": r.end_time,
            "time_elapsed": r.time_elapsed
        }
        for r in records
    ]
# =====================================================================
# API GỬI TRẠNG THÁI NGỌN LỬA XUỐNG DEVICE QUA MQTT
# =====================================================================
@router.post("/fire_update")
def update_fire_mqtt(payload_data: dict):
    fire_dict = payload_data.get("payload", {})
    
    if globals_var.mqtt_client:
        payload = json.dumps(fire_dict)
        globals_var.mqtt_client.publish("fire_data/14", payload)
        print(f"[MQTT] 🔥 Sent Fire Data message: {payload}")
        return {"status": "success"}
        
    return {"status": "error", "message": "MQTT not connected"}
# =====================================================================
# API VẼ VÀ QUẢN LÝ QUỸ ĐẠO (TRAJECTORY) BẰNG TIẾN TRÌNH ĐỘC LẬP
# =====================================================================
@router.get("/trajectory/plot")
def api_plot_trajectory_process():
    try:
        script_path = os.path.join(globals_var.ROOT_DIR, 'plot', 'draw_trajectory.py')
        
        subprocess.Popen(["python", script_path])
        
        return {"status": "success", "message": "Background plotting process triggered successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/trajectory/clear")
def api_clear_trajectory():
    csv_path = os.path.join(globals_var.ROOT_DIR, 'trajectory_log.csv')
    if os.path.exists(csv_path):
        os.remove(csv_path)
    return {"status": "cleared"}