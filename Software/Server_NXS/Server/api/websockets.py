import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import core.globals_var as globals_var

router = APIRouter()

# =====================================================================
# API KẾT NỐI WS ĐỂ BACKEND ĐẨY DỮ LIỆU DEVICES CHO FRONTEND
# =====================================================================
@router.websocket("/ws/devices")
async def websocket_devices_endpoint(websocket: WebSocket):
    await websocket.accept()
    globals_var.device_manager_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        globals_var.device_manager_websockets.remove(websocket)

# =====================================================================
# API KẾT NÔI WS ĐỂ BACKEND ĐẨY DỮ LIỆU VỊ TRÍ REAL-TIME CHO FRONTEND
# =====================================================================
@router.websocket("/ws/realtime_location")
async def websocket_realtime_endpoint(websocket: WebSocket):
    await websocket.accept()
    globals_var.active_websockets.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "sync_scores":
                    globals_var.CURRENT_SCORES.update(msg.get("scores", {}))
            except Exception:
                pass
    except WebSocketDisconnect:
        globals_var.active_websockets.remove(websocket)
        print("[Noti] ⚠️ A Client disconnected from Real-time Location")