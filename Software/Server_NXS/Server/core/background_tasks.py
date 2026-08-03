import asyncio
import database_models
from database import SessionLocal
import core.globals_var as globals_var


# Hàm lưu thiết bị mới phát hiện vào DB
def _save_new_device(device_type, hex_id):
    db = SessionLocal()
    try:
        if device_type == "UWB":
            new_dev = database_models.DeviceUWB(device_name=f"{hex_id}", device_hex_id=hex_id)
        else:
            new_dev = database_models.DeviceRSSI(device_name=f"{hex_id}", device_hex_id=hex_id)
        db.add(new_dev)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

# Hàm ghi dữ liệu từ buffer vào DB
def _bulk_save_to_db(uwb_list, rssi_list):
    if not uwb_list and not rssi_list: return
    db = SessionLocal()
    try:
        if uwb_list:
            db.bulk_save_objects(uwb_list) # bulk_save_objects: Cập nhật hàng loạt vào DB
        if rssi_list:
            db.bulk_save_objects(rssi_list)
        db.commit()
    except Exception as e:
        print(f"[Err] ❌ Bulk Save DB Error: {e}")
        db.rollback()
    finally:
        db.close()

# Task chạy định kỳ để lưu dữ liệu từ buffer vào DB mỗi 1 giây
async def periodic_db_save_task():
    while True:
        await asyncio.sleep(1.0)
        if globals_var.db_buffer_uwb or globals_var.db_buffer_rssi:
            
            uwb_to_save = globals_var.db_buffer_uwb[:]
            rssi_to_save = globals_var.db_buffer_rssi[:]
            globals_var.db_buffer_uwb.clear()
            globals_var.db_buffer_rssi.clear()
            
            # Đẩy lệnh lưu DB sang một Thread riêng để tránh block envent loop chính của FastAPI
            await asyncio.to_thread(_bulk_save_to_db, uwb_to_save, rssi_to_save)
