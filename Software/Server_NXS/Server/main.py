import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

import mqtt
import database_models
from database import SessionLocal, engine

import core.globals_var as globals_var
from core.background_tasks import periodic_db_save_task
from core.mqtt_handler import handle_incoming_mqtt_data
from api import routes, websockets

# HÀM KHỞI ĐỘNG SERVER (LIFESPAN)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load DB lên RAM 1 lần để lấy tọa độ
    db = SessionLocal()
    try:
        # Load danh sách thiết bị đã biết lên RAM
        for d in db.query(database_models.DeviceRSSI).all():
            globals_var.KNOWN_RSSI_DEVICES.add(d.device_hex_id)
        for d in db.query(database_models.DeviceUWB).all():
            globals_var.KNOWN_UWB_DEVICES.add(d.device_hex_id)

        uwb_latest_map = db.query(database_models.UwbMapInfo).order_by(database_models.UwbMapInfo.map_info_id.desc()).first()
        if uwb_latest_map and uwb_latest_map.beacon_location:
            globals_var.BEACONS_CONFIG = uwb_latest_map.beacon_location
            globals_var.CURRENT_UWB_CELL_LENGTH = (uwb_latest_map.area_of_one_unit or 1.0) ** 0.5
            print("[Noti] ✅ UWB locations have been loaded from the database into RAM cache!")
    finally:
        db.close()

    globals_var.data_queue = asyncio.Queue(maxsize=500)
    loop = asyncio.get_running_loop()

    # Task chạy ngầm ghi DB
    db_task = asyncio.create_task(periodic_db_save_task())
    
    # Khởi động kết nối MQTT
    mqtt.init_async_bridge(loop, handle_incoming_mqtt_data)
    globals_var.mqtt_client = mqtt.connect_mqtt()
    
    yield 
    
    # Đóng kết nối khi tắt server
    db_task.cancel()
    globals_var.mqtt_client.loop_stop()
    globals_var.mqtt_client.disconnect()

# Khởi tạp app Fast API
app = FastAPI(lifespan=lifespan)

# Cấu hình CORS
app.add_middleware( 
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tạo bảng trong DB nếu chưa tồn tại
database_models.Base.metadata.create_all(bind = engine)

# ĐĂNG KÝ ROUTER
app.include_router(websockets.router)
app.include_router(routes.router)