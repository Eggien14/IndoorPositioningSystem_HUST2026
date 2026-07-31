"""
FastAPI Main Application for Indoor Positioning System
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
import asyncio
import json
import os
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from backend import crud, database, models
from backend.mqtt_client import mqtt_client
from backend.mqtt_handle.fingerprints_collectdata import fingerprint_collector
from backend.mqtt_handle.trilateration_LM import trilateration_runtime
from backend.mqtt_handle.trilateration_uwb import uwb_runtime
from backend.mqtt_handle.transformer_pdr_eskf import algorithm3_runtime, model_exists
from backend.algorithm_3 import algorithm3_manager
from backend.algorithm_uwb import uwb_manager
from backend.mqtt_handle.server_2_device import publish_fire_data, publish_user_pos
from backend.run_history_csv import run_history_csv


app = FastAPI(
    title="Indoor Positioning System - Map, Training, Data Collection",
    description="Local web application for map management, training, devices, and fingerprint data collection",
    version="2.0.0"
)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
app.mount("/img", StaticFiles(directory="frontend/img"), name="img")
templates = Jinja2Templates(directory="frontend/templates")

active_training_runs: Dict[str, Dict[str, Any]] = {}

# Vòng lặp mô phỏng (lan/dập lửa + tính điểm) cho thuật toán 3 — mỗi run 1 asyncio task.
algo3_sim_tasks: Dict[str, "asyncio.Task"] = {}
ALGO3_TICK_SECONDS = 0.1   # ~10 Hz

# Vòng lặp mô phỏng cho thuật toán UWB (2 & 5) — mỗi run 1 asyncio task (giống algo 3).
uwb_sim_tasks: Dict[str, "asyncio.Task"] = {}

ALGORITHM_NAMES = {
    1: "RSSI Fingerprints - CNN + PDR",
    2: "Trilateration: Robust LM (loosely-coupled)",
    3: "RSSI Fingerprints - Transformer + PDR + ESKF",
    4: "RSSI Fingerprints - Multi modal cross attention",
    5: "Trilateration: Tightly-coupled EKF",
}

# Algorithms that localize from UWB ranging (need >=3 UWB beacons incl. >=1 master).
UWB_ALGORITHMS = (2, 5)


def role_name(role_id: int) -> str:
    return {1: "admin", 2: "trainer", 3: "trainee"}.get(role_id, "unknown")


def ensure_role_allowed(role_id: int, allowed: List[int]) -> None:
    if role_id not in allowed:
        raise HTTPException(status_code=403, detail="Permission denied")


@app.on_event("startup")
async def startup_event():
    print("=" * 60)
    print("Indoor Positioning System - Starting Up...")
    print("=" * 60)

    database.init_connection_pool()
    database.test_connection()
    mqtt_client.connect()

    print("=" * 60)
    print("Server ready")
    print("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    mqtt_client.disconnect()
    print("Server shutdown complete")


# ============================================================
# Frontend Routes
# ============================================================

@app.get("/", response_class=HTMLResponse)
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/home", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/map-customization", response_class=HTMLResponse)
@app.get("/choose-map", response_class=HTMLResponse)
async def choose_map_page(request: Request):
    return templates.TemplateResponse("choose_map.html", {"request": request})


@app.get("/create-map", response_class=HTMLResponse)
async def create_map_page(request: Request):
    return templates.TemplateResponse("create_map.html", {"request": request})


@app.get("/edit-map/{map_id}", response_class=HTMLResponse)
async def edit_map_page(request: Request, map_id: int):
    return templates.TemplateResponse("edit_map.html", {
        "request": request,
        "map_id": map_id
    })


@app.get("/collect-data/{map_id}", response_class=HTMLResponse)
async def collect_data_page(request: Request, map_id: int):
    return templates.TemplateResponse("collect_data.html", {
        "request": request,
        "map_id": map_id
    })


@app.get("/training-sessions", response_class=HTMLResponse)
async def training_sessions_page(request: Request):
    return templates.TemplateResponse("training_sessions.html", {"request": request})


@app.get("/training-sessions/{session_id}/editor", response_class=HTMLResponse)
async def session_editor_page(request: Request, session_id: int):
    return templates.TemplateResponse("session_editor.html", {
        "request": request,
        "session_id": session_id,
    })


@app.get("/devices", response_class=HTMLResponse)
async def devices_page(request: Request):
    return templates.TemplateResponse("devices.html", {"request": request})


@app.get("/training-select", response_class=HTMLResponse)
async def training_select_page(request: Request):
    return templates.TemplateResponse("training_select.html", {"request": request})


@app.get("/training-live", response_class=HTMLResponse)
@app.get("/training-live-test", response_class=HTMLResponse)
async def training_live_test_page(request: Request):
    return templates.TemplateResponse("training_live.html", {"request": request})


@app.get("/training-live-trilateration", response_class=HTMLResponse)
async def training_live_trilateration_page(request: Request):
    return templates.TemplateResponse("training_live_trilateration.html", {"request": request})


@app.get("/training-live-algorithm3", response_class=HTMLResponse)
async def training_live_algorithm3_page(request: Request):
    return templates.TemplateResponse("training_live_algorithm3.html", {"request": request})


@app.get("/training-live-algorithm2", response_class=HTMLResponse)
async def training_live_algorithm2_page(request: Request):
    # Trang realtime thuật toán 2 (UWB Trilateration LM) — clone trang algo 3.
    return templates.TemplateResponse("training_live_algorithm2.html", {"request": request})


@app.get("/training-live-algorithm5", response_class=HTMLResponse)
async def training_live_algorithm5_page(request: Request):
    # Trang realtime thuật toán 5 (UWB Tightly-coupled EKF) — clone trang algo 3.
    return templates.TemplateResponse("training_live_algorithm5.html", {"request": request})


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    return templates.TemplateResponse("history.html", {"request": request})


@app.get("/rickroll", response_class=HTMLResponse)
async def rickroll_page(request: Request):
    return templates.TemplateResponse("rickroll.html", {"request": request})


# ============================================================
# Auth API
# ============================================================

@app.post("/api/auth/login", response_model=models.LoginResponse)
async def login(data: models.LoginRequest):
    account = crud.validate_login(data.username, data.password)
    if not account:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return models.LoginResponse(
        username=account["username"],
        role_id=account["role_id"],
        role_name=role_name(account["role_id"])
    )


# ============================================================
# Existing Map API
# ============================================================

@app.get("/api/maps", response_model=List[models.MapResponse])
async def get_maps():
    try:
        return crud.get_all_maps()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/maps/{map_id}", response_model=models.MapResponse)
async def get_map(map_id: int):
    try:
        map_data = crud.get_map_by_id(map_id)
        if not map_data:
            raise HTTPException(status_code=404, detail="Map not found")
        return map_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/maps", response_model=models.SuccessResponse)
async def create_map(map_data: models.MapCreate):
    try:
        map_id = crud.create_map(map_data)
        return models.SuccessResponse(
            success=True,
            message="Map created successfully",
            data={"map_id": map_id}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/maps/{map_id}/offset-angle", response_model=models.SuccessResponse)
async def update_map_offset_angle(map_id: int, payload: models.MapOffsetUpdate):
    try:
        map_data = crud.get_map_by_id(map_id)
        if not map_data:
            raise HTTPException(status_code=404, detail="Map not found")

        crud.update_map_offset_angles(map_id, payload.offset_angles)
        return models.SuccessResponse(success=True, message="Map offset angle updated")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/maps/{map_id}", response_model=models.SuccessResponse)
async def delete_map(map_id: int):
    try:
        map_data = crud.get_map_by_id(map_id)
        if not map_data:
            raise HTTPException(status_code=404, detail="Map not found")

        crud.delete_map(map_id)
        return models.SuccessResponse(success=True, message="Map deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/maps/{map_id}/cells", response_model=List[models.CellResponse])
async def get_map_cells(map_id: int):
    try:
        return crud.get_map_cells(map_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/maps/{map_id}/send-map-mqtt")
async def send_map_to_mqtt(map_id: int):
    map_data = crud.get_map_by_id(map_id)
    if not map_data:
        raise HTTPException(status_code=404, detail="Map not found")

    cells = crud.get_map_cells(map_id)
    passable_cells = [
        [int(c["coord_x"]), int(c["coord_y"])]
        for c in cells
        if c.get("is_passable")
    ]

    payload = json.dumps({
        "info": {
            "x": int(map_data["length_x"]),
            "y": int(map_data["width_y"]),
            "north_offset": float(map_data.get("offset_angles", 0.0)),
        },
        "cells": passable_cells,
    })

    success = mqtt_client.publish("map_data", payload)
    if not success:
        raise HTTPException(status_code=503, detail="MQTT broker not connected")

    return {"success": True, "cells_count": len(passable_cells)}


@app.get("/api/algorithm-names")
async def get_algorithm_names():
    """Single source of truth for the 4 algorithm display names (FE reads this)."""
    return {str(k): v for k, v in ALGORITHM_NAMES.items()}


@app.get("/api/sim/spray-config")
async def get_spray_config():
    """Spray-cone geometry — single source of truth = `backend/simulation/extinguish.py`
    `SPRAY`. The realtime pages fetch this to DRAW the cone so the UI always matches the
    actual extinguish hit-detection (no more hardcoded/drifted values)."""
    from backend.simulation import extinguish as ext
    return {
        mode: {
            "half_angle_deg": float(cfg["half_angle_deg"]),
            "max_radius_m": float(cfg["max_radius_m"]),
        }
        for mode, cfg in ext.SPRAY.items()
    }


@app.get("/api/maps/{map_id}/beacons", response_model=List[models.MapBeaconResponse])
async def get_map_beacons(map_id: int):
    try:
        map_data = crud.get_map_by_id(map_id)
        if not map_data:
            raise HTTPException(status_code=404, detail="Map not found")
        return crud.get_map_beacons(map_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/maps/{map_id}/beacons", response_model=models.SuccessResponse)
async def create_map_beacon(map_id: int, payload: models.MapBeaconCreate):
    try:
        map_data = crud.get_map_by_id(map_id)
        if not map_data:
            raise HTTPException(status_code=404, detail="Map not found")

        if payload.beacon_type == 4:
            counts = crud.count_map_beacons_by_type(map_id)
            if counts.get(4, 0) >= 1:
                raise HTTPException(status_code=400, detail="Each map can only have one UWB master beacon")

        beacon_id = crud.create_map_beacon(
            map_id=map_id,
            beacon_hex_id=payload.beacon_hex_id,
            beacon_type=payload.beacon_type,
            coord_x=payload.coord_x,
            coord_y=payload.coord_y,
        )
        return models.SuccessResponse(success=True, message="Beacon created", data={"beacon_id": beacon_id})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/beacons/{beacon_id}", response_model=models.SuccessResponse)
async def update_map_beacon(beacon_id: int, payload: models.MapBeaconUpdate):
    try:
        beacon = crud.get_map_beacon_by_id(beacon_id)
        if not beacon:
            raise HTTPException(status_code=404, detail="Beacon not found")

        next_type = payload.beacon_type if payload.beacon_type is not None else int(beacon["beacon_type"])
        if next_type == 4 and int(beacon["beacon_type"]) != 4:
            counts = crud.count_map_beacons_by_type(int(beacon["map_id"]))
            if counts.get(4, 0) >= 1:
                raise HTTPException(status_code=400, detail="Each map can only have one UWB master beacon")

        crud.update_map_beacon(
            beacon_id=beacon_id,
            beacon_hex_id=payload.beacon_hex_id,
            beacon_type=payload.beacon_type,
            coord_x=payload.coord_x,
            coord_y=payload.coord_y,
        )
        return models.SuccessResponse(success=True, message="Beacon updated")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/beacons/{beacon_id}", response_model=models.SuccessResponse)
async def delete_map_beacon(beacon_id: int):
    try:
        beacon = crud.get_map_beacon_by_id(beacon_id)
        if not beacon:
            raise HTTPException(status_code=404, detail="Beacon not found")
        crud.delete_map_beacon(beacon_id)
        return models.SuccessResponse(success=True, message="Beacon deleted")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/maps/{map_id}/algorithms", response_model=List[models.MapAlgorithmResponse])
async def get_map_algorithms(map_id: int):
    try:
        map_data = crud.get_map_by_id(map_id)
        if not map_data:
            raise HTTPException(status_code=404, detail="Map not found")
        return crud.get_map_algorithms(map_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/maps/{map_id}/algorithms", response_model=models.SuccessResponse)
async def update_map_algorithms(map_id: int, payload: models.MapAlgorithmUpdate):
    try:
        map_data = crud.get_map_by_id(map_id)
        if not map_data:
            raise HTTPException(status_code=404, detail="Map not found")

        algorithms = sorted(set(payload.algorithms))
        invalid = [a for a in algorithms if a not in ALGORITHM_NAMES]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid algorithms: {invalid}")

        beacon_counts = crud.count_map_beacons_by_type(map_id)
        wifi_ble_total = beacon_counts.get(1, 0) + beacon_counts.get(2, 0)
        uwb_total = beacon_counts.get(3, 0) + beacon_counts.get(4, 0)
        uwb_master = beacon_counts.get(4, 0)

        fingerprint_algorithms = [1, 3, 4]
        if any(algorithm in algorithms for algorithm in fingerprint_algorithms) and wifi_ble_total < 3:
            raise HTTPException(status_code=400, detail="Fingerprint algorithms require at least 3 WiFi/BLE beacons")

        if any(a in algorithms for a in UWB_ALGORITHMS) and not (uwb_total >= 3 and uwb_master >= 1):
            raise HTTPException(
                status_code=400,
                detail="Trilateration algorithms require at least 3 UWB beacons including 1 UWB master",
            )

        crud.replace_map_algorithms(map_id, algorithms)
        return models.SuccessResponse(success=True, message="Map algorithms updated")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/cells/batch", response_model=models.SuccessResponse)
async def batch_update_cells(batch_update: models.CellBatchUpdate):
    try:
        cell_indices: Dict[int, int] = {}

        for cell_update in batch_update.cells:
            cell = crud.get_cell_by_id(cell_update.cell_id)
            if not cell:
                raise HTTPException(status_code=404, detail=f"Cell {cell_update.cell_id} not found")

            if cell_update.cell_index is not None:
                if cell_update.cell_index in cell_indices:
                    raise HTTPException(status_code=400, detail="Do not duplicate cell_index in batch")
                cell_indices[cell_update.cell_index] = cell_update.cell_id

        updated_count = crud.batch_update_cells(batch_update.cells)
        return models.SuccessResponse(
            success=True,
            message=f"Successfully updated {updated_count} cells"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/cells/{cell_id}", response_model=models.SuccessResponse)
async def update_cell(cell_id: int, cell_update: models.CellUpdate):
    try:
        cell = crud.get_cell_by_id(cell_id)
        if not cell:
            raise HTTPException(status_code=404, detail="Cell not found")

        if cell_update.cell_index is not None:
            if crud.check_duplicate_cell_index(cell["map_id"], cell_update.cell_index, cell_id):
                raise HTTPException(status_code=400, detail="Do not duplicate cell_index")

        crud.update_cell(cell_id, cell_update.cell_index, cell_update.is_passable)
        return models.SuccessResponse(success=True, message="Cell updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Existing Campaign + Fingerprint API
# ============================================================

@app.get("/api/maps/{map_id}/campaigns", response_model=List[models.CampaignResponse])
async def get_campaigns(map_id: int):
    try:
        return crud.get_campaigns_by_map(map_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/campaigns", response_model=models.SuccessResponse)
async def create_campaign(campaign_data: models.CampaignCreate):
    try:
        map_data = crud.get_map_by_id(campaign_data.map_id)
        if not map_data:
            raise HTTPException(status_code=404, detail="Map not found")

        campaign_id = crud.create_campaign(campaign_data)
        return models.SuccessResponse(
            success=True,
            message="Campaign created successfully",
            data={"campaign_id": campaign_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/campaigns/{campaign_id}", response_model=models.CampaignResponse)
async def get_campaign(campaign_id: int):
    try:
        campaign = crud.get_campaign_by_id(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return campaign
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/campaigns/{campaign_id}", response_model=models.SuccessResponse)
async def delete_campaign(campaign_id: int):
    try:
        campaign = crud.get_campaign_by_id(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        crud.delete_campaign(campaign_id)
        return models.SuccessResponse(success=True, message="Campaign deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/campaigns/{campaign_id}/statistics")
async def get_campaign_statistics(campaign_id: int):
    try:
        return crud.get_campaign_statistics(campaign_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/fingerprints", response_model=models.SuccessResponse)
async def create_fingerprint(fingerprint_data: models.FingerprintCreate):
    try:
        fingerprint_id = crud.create_fingerprint(fingerprint_data)
        return models.SuccessResponse(
            success=True,
            message="Fingerprint data saved",
            data={"fingerprint_id": fingerprint_id}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cells/{cell_id}/sample-count")
async def get_cell_sample_count(cell_id: int, campaign_id: int):
    try:
        count = crud.get_cell_sample_count(campaign_id, cell_id)
        return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/campaigns/{campaign_id}/cells/{cell_id}/fingerprints", response_model=List[models.FingerprintDetailResponse])
async def get_cell_fingerprints(campaign_id: int, cell_id: int):
    try:
        campaign = crud.get_campaign_by_id(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return crud.get_cell_fingerprints(campaign_id, cell_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/campaigns/{campaign_id}/cells/{cell_id}/fingerprints", response_model=models.SuccessResponse)
async def reset_cell_fingerprints(campaign_id: int, cell_id: int):
    try:
        campaign = crud.get_campaign_by_id(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        deleted_count = crud.delete_cell_fingerprints(campaign_id, cell_id)
        return models.SuccessResponse(
            success=True,
            message="Cell data reset successfully",
            data={"deleted_count": deleted_count}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data-collection/start")
async def start_data_collection(request: Dict[str, Any]):
    try:
        campaign_id = request.get("campaign_id")
        cell_id = request.get("cell_id")
        mqtt_topic = str(request.get("mqtt_topic", "")).strip()
        if campaign_id is None or cell_id is None or not mqtt_topic:
            raise HTTPException(status_code=400, detail="Missing required parameters")

        session_key = fingerprint_collector.start(
            campaign_id=int(campaign_id),
            cell_id=int(cell_id),
            mqtt_topic=mqtt_topic,
        )
        return models.SuccessResponse(
            success=True,
            message="Data collection started",
            data={"session_key": session_key}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data-collection/stop")
async def stop_data_collection(request: Dict[str, Any]):
    try:
        session_key = request.get("session_key")
        if not session_key:
            raise HTTPException(status_code=404, detail="Collection session not found")

        final_count = fingerprint_collector.stop(str(session_key))

        return models.SuccessResponse(
            success=True,
            message="Data collection stopped",
            data={"samples_collected": final_count}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data-collection/status/{session_key}")
async def get_collection_status(session_key: str):
    return fingerprint_collector.get_status(session_key)


# ============================================================
# Device API
# ============================================================

@app.get("/api/devices", response_model=List[models.DeviceResponse])
async def get_devices():
    try:
        return crud.get_all_devices()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/devices", response_model=models.SuccessResponse)
async def create_device(device_data: models.DeviceCreate, role_id: int):
    ensure_role_allowed(role_id, [1, 2])
    try:
        device_id = crud.create_device(device_data)
        return models.SuccessResponse(
            success=True,
            message="Device created successfully",
            data={"device_id": device_id}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/devices/{device_id}", response_model=models.SuccessResponse)
async def update_device(device_id: int, device_data: models.DeviceUpdate, role_id: int):
    ensure_role_allowed(role_id, [1, 2])
    try:
        current = crud.get_device_by_id(device_id)
        if not current:
            raise HTTPException(status_code=404, detail="Device not found")

        crud.update_device(device_id, device_data)
        return models.SuccessResponse(success=True, message="Device updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/devices/{device_id}", response_model=models.SuccessResponse)
async def delete_device(device_id: int, role_id: int):
    ensure_role_allowed(role_id, [1, 2])
    try:
        current = crud.get_device_by_id(device_id)
        if not current:
            raise HTTPException(status_code=404, detail="Device not found")

        crud.delete_device(device_id)
        return models.SuccessResponse(success=True, message="Device deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Session API (Create Exercise)
# ============================================================

@app.get("/api/sessions", response_model=List[models.SessionResponse])
async def get_sessions():
    try:
        return crud.get_all_sessions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/maps/{map_id}/sessions", response_model=List[models.SessionResponse])
async def get_sessions_by_map(map_id: int):
    try:
        return crud.get_sessions_by_map(map_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}", response_model=models.SessionResponse)
async def get_session(session_id: int):
    try:
        session = crud.get_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions", response_model=models.SuccessResponse)
async def create_session(session_data: models.SessionCreate, role_id: int):
    ensure_role_allowed(role_id, [1, 2])
    try:
        map_data = crud.get_map_by_id(session_data.map_id)
        if not map_data:
            raise HTTPException(status_code=404, detail="Map not found")

        session_id = crud.create_session(session_data)
        return models.SuccessResponse(
            success=True,
            message="Session created successfully",
            data={"session_id": session_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/sessions/{session_id}", response_model=models.SuccessResponse)
async def update_session(session_id: int, session_data: models.SessionUpdate, role_id: int):
    ensure_role_allowed(role_id, [1, 2])
    try:
        current = crud.get_session_by_id(session_id)
        if not current:
            raise HTTPException(status_code=404, detail="Session not found")

        crud.update_session(session_id, session_data)
        return models.SuccessResponse(success=True, message="Session updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/sessions/{session_id}", response_model=models.SuccessResponse)
async def delete_session(session_id: int, role_id: int):
    ensure_role_allowed(role_id, [1, 2])
    try:
        current = crud.get_session_by_id(session_id)
        if not current:
            raise HTTPException(status_code=404, detail="Session not found")

        crud.delete_session(session_id)
        return models.SuccessResponse(success=True, message="Session deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Session Fire API
# ============================================================

@app.get("/api/sessions/{session_id}/fires", response_model=List[models.SessionFireResponse])
async def get_session_fires(session_id: int):
    try:
        session = crud.get_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return crud.get_session_fires(session_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions/{session_id}/fires", response_model=models.SuccessResponse)
async def create_session_fire(session_id: int, fire_data: models.SessionFireCreate, role_id: int):
    ensure_role_allowed(role_id, [1, 2])
    try:
        session = crud.get_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if fire_data.session_id != session_id:
            raise HTTPException(status_code=400, detail="Session ID mismatch")

        cell = crud.find_cell_by_map_and_coord(session["map_id"], fire_data.coord_x, fire_data.coord_y)
        if not cell:
            raise HTTPException(status_code=404, detail="Cell not found at given coordinates")

        fire_id = crud.create_session_fire(
            session_id=session_id,
            fire_time_seconds=fire_data.fire_time_seconds,
            fire_level=fire_data.fire_level,
            fire_spread=fire_data.fire_spread,
            fire_spread_time=fire_data.fire_spread_time,
            cell_index=cell["cell_index"],
            coord_x=cell["coord_x"],
            coord_y=cell["coord_y"],
        )

        return models.SuccessResponse(
            success=True,
            message="Fire event added",
            data={"session_fire_id": fire_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions/{session_id}/fires/by-cell", response_model=models.SuccessResponse)
async def create_session_fire_by_cell(session_id: int, fire_data: models.SessionFireClickCreate, role_id: int):
    ensure_role_allowed(role_id, [1, 2])
    try:
        session = crud.get_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if fire_data.session_id != session_id:
            raise HTTPException(status_code=400, detail="Session ID mismatch")

        cell = crud.get_cell_by_id(fire_data.cell_id)
        if not cell or cell["map_id"] != session["map_id"]:
            raise HTTPException(status_code=404, detail="Cell not found for this session map")

        fire_id = crud.create_session_fire(
            session_id=session_id,
            fire_time_seconds=fire_data.fire_time_seconds,
            fire_level=fire_data.fire_level,
            fire_spread=fire_data.fire_spread,
            fire_spread_time=fire_data.fire_spread_time,
            cell_index=cell["cell_index"],
            coord_x=cell["coord_x"],
            coord_y=cell["coord_y"],
        )

        return models.SuccessResponse(
            success=True,
            message="Fire event added",
            data={"session_fire_id": fire_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/session-fires/{session_fire_id}", response_model=models.SuccessResponse)
async def delete_session_fire(session_fire_id: int, role_id: int):
    ensure_role_allowed(role_id, [1, 2])
    try:
        deleted = crud.delete_session_fire(session_fire_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Fire event not found")
        return models.SuccessResponse(success=True, message="Fire event deleted")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Training + History API
# ============================================================

@app.post("/api/training/start", response_model=models.SuccessResponse)
async def start_training(request: models.TrainingStartRequest):
    try:
        account = crud.get_account_by_username(request.username)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        if account["role_id"] != request.role_id:
            raise HTTPException(status_code=403, detail="Role mismatch")

        if request.role_id == 3 and len(request.device_ids) != 1:
            raise HTTPException(status_code=400, detail="Trainee can only select one device")

        map_data = crud.get_map_by_id(request.map_id)
        if not map_data:
            raise HTTPException(status_code=404, detail="Map not found")

        available_algorithms = [row["algorithm"] for row in crud.get_map_algorithms(request.map_id)]
        if request.algorithm not in available_algorithms:
            raise HTTPException(status_code=400, detail="Selected algorithm is not enabled for this map")

        session_data: Optional[Dict[str, Any]] = None
        fires: List[Dict[str, Any]] = []

        if request.session_id is not None:
            session_data = crud.get_session_by_id(request.session_id)
            if not session_data or session_data["map_id"] != request.map_id:
                raise HTTPException(status_code=404, detail="Session not found for this map")
            fires = crud.get_session_fires(request.session_id)

        for device_id in request.device_ids:
            if not crud.get_device_by_id(device_id):
                raise HTTPException(status_code=404, detail=f"Device {device_id} not found")

        training_run_id = str(uuid.uuid4())
        active_training_runs[training_run_id] = {
            "training_run_id": training_run_id,
            "username": request.username,
            "role_id": request.role_id,
            "map_id": request.map_id,
            "session_id": request.session_id,
            "algorithm": request.algorithm,
            "algorithm_name": ALGORITHM_NAMES[request.algorithm],
            "device_ids": request.device_ids,
            "fires": fires,
            "duration_seconds": session_data["duration_seconds"] if session_data else 0,
            "status": "prepared",
            "prepared_at_unix": time.time(),
            "started_at_unix": None,
        }

        return models.SuccessResponse(
            success=True,
            message="Training prepared",
            data={
                "training_run_id": training_run_id,
                "map_id": request.map_id,
                "session": session_data,
                "fires": fires,
                "algorithm": request.algorithm,
                "algorithm_name": ALGORITHM_NAMES[request.algorithm],
                "realtime": None,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/training/{training_run_id}/start", response_model=models.SuccessResponse)
async def begin_training(training_run_id: str):
    run = active_training_runs.get(training_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Training run not found")

    if run.get("status") == "running" and run.get("started_at_unix"):
        return models.SuccessResponse(
            success=True,
            message="Training already started",
            data={"training_run_id": training_run_id, "started_at_unix": run["started_at_unix"]},
        )

    run["status"] = "running"
    run["started_at_unix"] = time.time()

    realtime_payload: Optional[Dict[str, Any]] = None
    if run.get("algorithm") == 2:
        try:
            realtime_payload = trilateration_runtime.start(
                training_run_id=training_run_id,
                map_id=run["map_id"],
                selected_device_ids=run["device_ids"],
            )
        except ValueError as error:
            run["status"] = "prepared"
            run["started_at_unix"] = None
            raise HTTPException(status_code=400, detail=str(error))

    return models.SuccessResponse(
        success=True,
        message="Training started",
        data={
            "training_run_id": training_run_id,
            "started_at_unix": run["started_at_unix"],
            "realtime": realtime_payload,
        },
    )


@app.get("/api/training/{training_run_id}")
async def get_training_state(training_run_id: str):
    state = active_training_runs.get(training_run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Training run not found")
    return state


@app.get("/api/training-lm/{training_run_id}/state")
async def get_training_lm_state(training_run_id: str):
    state = active_training_runs.get(training_run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Training run not found")
    if state.get("algorithm") != 2:
        raise HTTPException(status_code=400, detail="This training run is not trilateration LM")

    try:
        return trilateration_runtime.get_state(training_run_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


# ------------------------------------------------------------
# Algorithm 3 (Transformer + PDR + ESKF) realtime
# ------------------------------------------------------------

@app.get("/api/training-alg3/maps/{map_id}/models")
async def list_algorithm3_models(map_id: int):
    """Danh sách campaign của map kèm cờ đã có model transformer huấn luyện hay chưa.

    Trang realtime dùng để cho người dùng chọn đúng model (transformer_model.pt).
    """
    if not crud.get_map_by_id(map_id):
        raise HTTPException(status_code=404, detail="Map not found")
    campaigns = crud.get_campaigns_by_map(map_id)
    return [
        {
            "campaign_id": c["campaign_id"],
            "campaign_name": c.get("campaign_name"),
            "sample_number": c.get("sample_number"),
            "has_model": model_exists(map_id, c["campaign_id"]),
        }
        for c in campaigns
    ]


def _save_algorithm3_history(training_run_id: str, outcome: Optional[Dict[str, Any]]) -> None:
    """Lưu session_history khi lượt chạy algo 3 KẾT THÚC TỰ NHIÊN (không lưu khi Stop)."""
    run = active_training_runs.get(training_run_id)
    if not run or run.get("history_saved") or run.get("session_id") is None:
        return
    started_at = run.get("started_at_unix") or run.get("prepared_at_unix") or time.time()
    elapsed = int(max(0, time.time() - started_at))
    score_by_device = {d["device_id"]: d["score"] for d in algorithm3_manager.device_scores(training_run_id)}
    for device_id in run["device_ids"]:
        crud.create_session_history(
            models.SessionHistoryCreate(
                username=run["username"],
                device_id=device_id,
                session_id=run["session_id"],
                completion_seconds=elapsed,
                score=int(score_by_device.get(device_id, 0)),
            )
        )
    run["history_saved"] = True
    run["outcome"] = outcome


ALGO3_USER_POS_PERIOD = 1.0   # giây: nhịp đẩy lại user_pos khi điểm đổi (dù đứng yên)


async def _algorithm3_sim_loop(training_run_id: str) -> None:
    """Vòng lặp mô phỏng: tick sim, publish fire_data, đẩy user_pos khi điểm đổi,
    lưu history khi kết thúc tự nhiên."""
    last = time.monotonic()
    since_pos = 0.0
    last_pub: Dict[str, tuple] = {}
    try:
        while True:
            await asyncio.sleep(ALGO3_TICK_SECONDS)
            now = time.monotonic()
            dt = now - last
            last = now

            run = active_training_runs.get(training_run_id)
            if not run or run.get("status") != "running":
                break

            result = algorithm3_manager.tick_simulation(training_run_id, dt)

            if result is not None:
                # fire_data — fires_num do sim quyết định (đúng quy tắc 2 tin của spec).
                if result.get("map_changed") and result.get("fires") is not None:
                    publish_fire_data(result.get("fires_num", 0), result["fires"])

                if result.get("ended"):
                    # Tin kết thúc: báo fires_num=0 (đóng đúng quy tắc 2 tin của spec
                    # ngay cả khi lượt chạy kết thúc cùng tick ngọn lửa cuối tắt).
                    publish_fire_data(0, [])
                    _save_algorithm3_history(training_run_id, result.get("outcome"))
                    break

            # user_pos định kỳ (cả creative lẫn session). Creative: score=None -> 0.
            since_pos += dt
            if since_pos >= ALGO3_USER_POS_PERIOD:
                since_pos = 0.0
                state = algorithm3_manager.get_state(training_run_id)
                for tag in state.get("tags", []):
                    hex_id = tag.get("tag_hex_id")
                    score = tag.get("score")
                    px, py = tag.get("position_x"), tag.get("position_y")
                    if hex_id is None or px is None:
                        continue
                    if score is None:
                        score = 0
                    snap = (round(float(px), 3), round(float(py), 3), score)
                    if last_pub.get(hex_id) != snap:
                        publish_user_pos(hex_id, px, py, score)
                        last_pub[hex_id] = snap
    except asyncio.CancelledError:
        pass
    finally:
        algo3_sim_tasks.pop(training_run_id, None)


@app.post("/api/training-alg3/{training_run_id}/start", response_model=models.SuccessResponse)
async def begin_training_algorithm3(training_run_id: str, request: models.Algorithm3StartRequest):
    run = active_training_runs.get(training_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Training run not found")
    if run.get("algorithm") != 3:
        raise HTTPException(status_code=400, detail="This training run is not Algorithm 3")

    assembly_point = None
    if request.assembly_x is not None and request.assembly_y is not None:
        assembly_point = (int(request.assembly_x), int(request.assembly_y))

    try:
        realtime_payload = algorithm3_runtime.start(
            training_run_id=training_run_id,
            map_id=run["map_id"],
            selected_device_ids=run["device_ids"],
            campaign_id=request.campaign_id,
            start_x=request.start_x,
            start_y=request.start_y,
            offset_angle_bno=request.offset_angle_bno,
            root_fires=run.get("fires") or [],
            duration_seconds=run.get("duration_seconds") or 0,
            assembly_point=assembly_point,
            admin_enabled=request.admin_enabled,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    run["status"] = "running"
    run["started_at_unix"] = time.time()
    run["campaign_id"] = request.campaign_id
    run["save_history"] = bool(request.save_history)
    if run["save_history"]:
        run_history_csv.start(training_run_id, run["map_id"], 3)

    # Vòng lặp định kỳ: sim (nếu có session) + luôn đẩy user_pos (kể cả creative).
    if training_run_id not in algo3_sim_tasks:
        algo3_sim_tasks[training_run_id] = asyncio.create_task(_algorithm3_sim_loop(training_run_id))

    return models.SuccessResponse(
        success=True,
        message="Algorithm 3 training started",
        data={
            "training_run_id": training_run_id,
            "started_at_unix": run["started_at_unix"],
            "campaign_id": request.campaign_id,
            "realtime": realtime_payload,
        },
    )


@app.get("/api/training-alg3/{training_run_id}/state")
async def get_training_algorithm3_state(training_run_id: str):
    state = active_training_runs.get(training_run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Training run not found")
    if state.get("algorithm") != 3:
        raise HTTPException(status_code=400, detail="This training run is not Algorithm 3")
    try:
        return algorithm3_runtime.get_state(training_run_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@app.post("/api/training-alg3/{training_run_id}/admin", response_model=models.SuccessResponse)
async def set_algorithm3_admin_state(training_run_id: str, request: models.Algorithm3AdminState):
    """Người điều khiển trên màn hình server đẩy trạng thái thiết bị ADMIN ảo lên."""
    state = active_training_runs.get(training_run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Training run not found")
    if state.get("algorithm") != 3:
        raise HTTPException(status_code=400, detail="This training run is not Algorithm 3")
    algorithm3_manager.set_admin_state(training_run_id, request.model_dump())
    return models.SuccessResponse(success=True, message="Admin state updated")


# ------------------------------------------------------------
# Algorithm 2 (Trilateration Robust LM) + Algorithm 5 (Tightly-coupled EKF) realtime
# Cùng một pipeline UWB: 2 endpoint set (-alg2/-alg5) là wrapper mỏng gọi helper chung;
# brain (Algorithm2/Algorithm5) chọn theo `run["algorithm"]` trong uwb_runtime.start.
# Phần GỬI (user_pos/fire_data) + mô phỏng + ADMIN ảo Y HỆT algo 3.
# ------------------------------------------------------------

def _save_uwb_history(training_run_id: str, outcome: Optional[Dict[str, Any]]) -> None:
    """Lưu session_history khi lượt chạy UWB KẾT THÚC TỰ NHIÊN (không lưu khi Stop)."""
    run = active_training_runs.get(training_run_id)
    if not run or run.get("history_saved") or run.get("session_id") is None:
        return
    started_at = run.get("started_at_unix") or run.get("prepared_at_unix") or time.time()
    elapsed = int(max(0, time.time() - started_at))
    score_by_device = {d["device_id"]: d["score"] for d in uwb_manager.device_scores(training_run_id)}
    for device_id in run["device_ids"]:
        crud.create_session_history(
            models.SessionHistoryCreate(
                username=run["username"],
                device_id=device_id,
                session_id=run["session_id"],
                completion_seconds=elapsed,
                score=int(score_by_device.get(device_id, 0)),
            )
        )
    run["history_saved"] = True
    run["outcome"] = outcome


async def _uwb_sim_loop(training_run_id: str) -> None:
    """Vòng lặp mô phỏng UWB: tick sim, publish fire_data, đẩy user_pos khi điểm đổi,
    lưu history khi kết thúc tự nhiên. (Giống `_algorithm3_sim_loop`, đổi sang uwb_manager.)"""
    last = time.monotonic()
    since_pos = 0.0
    last_pub: Dict[str, tuple] = {}
    try:
        while True:
            await asyncio.sleep(ALGO3_TICK_SECONDS)
            now = time.monotonic()
            dt = now - last
            last = now

            run = active_training_runs.get(training_run_id)
            if not run or run.get("status") != "running":
                break

            result = uwb_manager.tick_simulation(training_run_id, dt)

            if result is not None:
                if result.get("map_changed") and result.get("fires") is not None:
                    publish_fire_data(result.get("fires_num", 0), result["fires"])

                if result.get("ended"):
                    publish_fire_data(0, [])
                    _save_uwb_history(training_run_id, result.get("outcome"))
                    break

            # user_pos định kỳ (cả creative lẫn session). Creative: score=None -> 0.
            since_pos += dt
            if since_pos >= ALGO3_USER_POS_PERIOD:
                since_pos = 0.0
                state = uwb_manager.get_state(training_run_id)
                for tag in state.get("tags", []):
                    hex_id = tag.get("tag_hex_id")
                    score = tag.get("score")
                    px, py = tag.get("position_x"), tag.get("position_y")
                    if hex_id is None or px is None:
                        continue
                    if score is None:
                        score = 0
                    snap = (round(float(px), 3), round(float(py), 3), score)
                    if last_pub.get(hex_id) != snap:
                        publish_user_pos(hex_id, px, py, score)
                        last_pub[hex_id] = snap
    except asyncio.CancelledError:
        pass
    finally:
        uwb_sim_tasks.pop(training_run_id, None)


def _uwb_begin(training_run_id: str, request: "models.UWBStartRequest", expected_algorithm: int):
    run = active_training_runs.get(training_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Training run not found")
    if run.get("algorithm") != expected_algorithm:
        raise HTTPException(status_code=400, detail=f"This training run is not Algorithm {expected_algorithm}")

    assembly_point = None
    if request.assembly_x is not None and request.assembly_y is not None:
        assembly_point = (int(request.assembly_x), int(request.assembly_y))

    try:
        realtime_payload = uwb_runtime.start(
            training_run_id=training_run_id,
            algorithm=expected_algorithm,
            map_id=run["map_id"],
            selected_device_ids=run["device_ids"],
            start_x=request.start_x,
            start_y=request.start_y,
            root_fires=run.get("fires") or [],
            duration_seconds=run.get("duration_seconds") or 0,
            assembly_point=assembly_point,
            admin_enabled=request.admin_enabled,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    run["status"] = "running"
    run["started_at_unix"] = time.time()
    run["save_history"] = bool(request.save_history)
    if run["save_history"]:
        run_history_csv.start(training_run_id, run["map_id"], expected_algorithm)

    if training_run_id not in uwb_sim_tasks:
        uwb_sim_tasks[training_run_id] = asyncio.create_task(_uwb_sim_loop(training_run_id))

    return models.SuccessResponse(
        success=True,
        message=f"Algorithm {expected_algorithm} training started",
        data={
            "training_run_id": training_run_id,
            "started_at_unix": run["started_at_unix"],
            "realtime": realtime_payload,
        },
    )


def _uwb_state(training_run_id: str, expected_algorithm: int):
    state = active_training_runs.get(training_run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Training run not found")
    if state.get("algorithm") != expected_algorithm:
        raise HTTPException(status_code=400, detail=f"This training run is not Algorithm {expected_algorithm}")
    try:
        return uwb_runtime.get_state(training_run_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


def _uwb_admin(training_run_id: str, request: "models.Algorithm3AdminState", expected_algorithm: int):
    state = active_training_runs.get(training_run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Training run not found")
    if state.get("algorithm") != expected_algorithm:
        raise HTTPException(status_code=400, detail=f"This training run is not Algorithm {expected_algorithm}")
    uwb_manager.set_admin_state(training_run_id, request.model_dump())
    return models.SuccessResponse(success=True, message="Admin state updated")


@app.post("/api/training-alg2/{training_run_id}/start", response_model=models.SuccessResponse)
async def begin_training_algorithm2(training_run_id: str, request: models.UWBStartRequest):
    return _uwb_begin(training_run_id, request, expected_algorithm=2)


@app.get("/api/training-alg2/{training_run_id}/state")
async def get_training_algorithm2_state(training_run_id: str):
    return _uwb_state(training_run_id, expected_algorithm=2)


@app.post("/api/training-alg2/{training_run_id}/admin", response_model=models.SuccessResponse)
async def set_algorithm2_admin_state(training_run_id: str, request: models.Algorithm3AdminState):
    return _uwb_admin(training_run_id, request, expected_algorithm=2)


@app.post("/api/training-alg5/{training_run_id}/start", response_model=models.SuccessResponse)
async def begin_training_algorithm5(training_run_id: str, request: models.UWBStartRequest):
    return _uwb_begin(training_run_id, request, expected_algorithm=5)


@app.get("/api/training-alg5/{training_run_id}/state")
async def get_training_algorithm5_state(training_run_id: str):
    return _uwb_state(training_run_id, expected_algorithm=5)


@app.post("/api/training-alg5/{training_run_id}/admin", response_model=models.SuccessResponse)
async def set_algorithm5_admin_state(training_run_id: str, request: models.Algorithm3AdminState):
    return _uwb_admin(training_run_id, request, expected_algorithm=5)


@app.post("/api/training/finish", response_model=models.SuccessResponse)
async def finish_training(request: models.TrainingFinishRequest):
    run = active_training_runs.get(request.training_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Training run not found")

    started_at = run.get("started_at_unix") or run.get("prepared_at_unix") or time.time()
    elapsed = int(max(0, time.time() - started_at))

    # Algo 3 + UWB (2,5): session_history do vòng lặp mô phỏng tự lưu khi KẾT THÚC TỰ NHIÊN.
    # finish ở đây = dọn dẹp / dừng khẩn cấp (Stop) -> KHÔNG lưu lại.
    sim_based = (3,) + UWB_ALGORITHMS   # (3, 2, 5)
    saved_history_ids: List[int] = []
    if run["session_id"] is not None and run.get("algorithm") not in sim_based:
        for device_id in run["device_ids"]:
            history_id = crud.create_session_history(
                models.SessionHistoryCreate(
                    username=run["username"],
                    device_id=device_id,
                    session_id=run["session_id"],
                    completion_seconds=elapsed,
                    score=request.score,
                )
            )
            saved_history_ids.append(history_id)

    if run.get("algorithm") in UWB_ALGORITHMS:
        task = uwb_sim_tasks.pop(request.training_run_id, None)
        if task:
            task.cancel()
        uwb_runtime.remove(request.training_run_id)
        # Dọn cả runtime trang algo-2 CŨ nếu lượt chạy đó dùng đường cũ (no-op nếu không).
        if run.get("algorithm") == 2:
            trilateration_runtime.remove(request.training_run_id)
    elif run.get("algorithm") == 3:
        task = algo3_sim_tasks.pop(request.training_run_id, None)
        if task:
            task.cancel()
        algorithm3_runtime.remove(request.training_run_id)

    csv_path = run_history_csv.finalize(request.training_run_id)

    del active_training_runs[request.training_run_id]

    return models.SuccessResponse(
        success=True,
        message="Training finished",
        data={"elapsed": elapsed, "history_ids": saved_history_ids, "csv_path": str(csv_path) if csv_path else None}
    )


@app.get("/api/history", response_model=List[models.SessionHistoryResponse])
async def get_history():
    try:
        return crud.get_all_session_history()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Health
# ============================================================

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "mqtt_connected": mqtt_client.is_connected
    }


if __name__ == "__main__":
    server_host = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port = int(os.getenv("SERVER_PORT", 8000))

    uvicorn.run(
        "backend.main:app",
        host=server_host,
        port=server_port,
        reload=True
    )
