"""
Pydantic models for Indoor Positioning System
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ============================================================
# Map Models
# ============================================================

class MapCreate(BaseModel):
    """Model for creating a new map"""
    map_name: str = Field(..., min_length=1, max_length=100)
    length_x: int = Field(..., gt=0, description="Number of cells along X-axis")
    width_y: int = Field(..., gt=0, description="Number of cells along Y-axis")
    offset_angles: float = Field(0.0, ge=0, lt=360, description="Clockwise map offset from true north")


class MapOffsetUpdate(BaseModel):
    offset_angles: float = Field(..., ge=0, lt=360)


class MapResponse(BaseModel):
    """Model for map response"""
    map_id: int
    map_name: str
    length_x: int
    width_y: int
    offset_angles: float
    created_at: datetime


# ============================================================
# Map Cell Models
# ============================================================

class CellUpdate(BaseModel):
    """Model for updating a cell"""
    cell_id: int
    cell_index: Optional[int] = None
    is_passable: Optional[int] = None


class CellResponse(BaseModel):
    """Model for cell response"""
    cell_id: int
    map_id: int
    cell_index: int
    coord_x: int
    coord_y: int
    is_passable: int


class CellBatchUpdate(BaseModel):
    """Model for batch updating multiple cells"""
    cells: List[CellUpdate]


# ============================================================
# Campaign Models
# ============================================================

class CampaignCreate(BaseModel):
    """Model for creating a new campaign"""
    map_id: int
    sample_number: int = Field(..., ge=0)
    campaign_name: Optional[str] = Field(None, max_length=100)


class CampaignResponse(BaseModel):
    """Model for campaign response"""
    campaign_id: int
    map_id: int
    sample_number: int
    campaign_name: Optional[str]
    measured_at: datetime


# ============================================================
# Fingerprint Data Models
# ============================================================

class FingerprintCreate(BaseModel):
    """Model for creating fingerprint data"""
    campaign_id: int
    cell_id: int
    
    # WiFi RSSI
    wifi_rssi_1: Optional[int] = None
    wifi_rssi_2: Optional[int] = None
    wifi_rssi_3: Optional[int] = None
    wifi_rssi_4: Optional[int] = None
    
    # BLE RSSI
    ble_rssi_1: Optional[int] = None
    ble_rssi_2: Optional[int] = None
    ble_rssi_3: Optional[int] = None
    ble_rssi_4: Optional[int] = None
    
    # Accelerometer
    acc_x: Optional[float] = None
    acc_y: Optional[float] = None
    acc_z: Optional[float] = None
    
    # Gyroscope
    gyro_x: Optional[float] = None
    gyro_y: Optional[float] = None
    gyro_z: Optional[float] = None
    
    # Magnetometer
    mag_x: Optional[float] = None
    mag_y: Optional[float] = None
    mag_z: Optional[float] = None
    
    # Orientation
    yaw: Optional[float] = None
    roll: Optional[float] = None
    pitch: Optional[float] = None


class FingerprintMQTTData(BaseModel):
    """Model for parsing MQTT fingerprint data (semicolon-separated)"""
    raw_data: str  # Format: wifi1;wifi2;wifi3;wifi4;ble1;ble2;ble3;ble4;accx;accy;accz;gyrox;gyroy;gyroz;magx;magy;magz;yaw;roll;pitch


class FingerprintResponse(BaseModel):
    """Model for fingerprint response"""
    fingerprint_id: int
    campaign_id: int
    cell_id: int
    collected_at: datetime


class FingerprintDetailResponse(FingerprintCreate):
    """Model for detailed fingerprint response"""
    fingerprint_id: int
    collected_at: datetime


# ============================================================
# Account, Device, Training Session Models
# ============================================================

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=255)


class LoginResponse(BaseModel):
    username: str
    role_id: int
    role_name: str


class AccountResponse(BaseModel):
    username: str
    role_id: int
    created_at: datetime


class DeviceCreate(BaseModel):
    device_name: str = Field(..., min_length=1, max_length=100)
    device_hex_id: str = Field(..., min_length=3, max_length=32)
    # Bình nước: -1 = vô hạn; >=0 = dung tích hữu hạn (mặc định 100 = WATER_MAX của sim).
    water_capacity: int = Field(100, ge=-1)


class DeviceUpdate(BaseModel):
    device_name: Optional[str] = Field(None, min_length=1, max_length=100)
    device_hex_id: Optional[str] = Field(None, min_length=3, max_length=32)
    water_capacity: Optional[int] = Field(None, ge=-1)


class DeviceResponse(BaseModel):
    device_id: int
    device_name: str
    device_hex_id: str
    water_capacity: int = 100      # -1 = vô hạn
    created_at: datetime


class MapBeaconCreate(BaseModel):
    beacon_hex_id: str = Field(..., min_length=3, max_length=32)
    beacon_type: int = Field(..., ge=1, le=4)
    coord_x: float
    coord_y: float


class MapBeaconUpdate(BaseModel):
    beacon_hex_id: Optional[str] = Field(None, min_length=3, max_length=32)
    beacon_type: Optional[int] = Field(None, ge=1, le=4)
    coord_x: Optional[float] = None
    coord_y: Optional[float] = None


class MapBeaconResponse(BaseModel):
    beacon_id: int
    map_id: int
    beacon_hex_id: str
    beacon_type: int
    coord_x: float
    coord_y: float
    created_at: datetime


class MapAlgorithmUpdate(BaseModel):
    algorithms: List[int]


class MapAlgorithmResponse(BaseModel):
    map_id: int
    algorithm: int
    created_at: datetime


class SessionCreate(BaseModel):
    session_name: str = Field(..., min_length=1, max_length=100)
    map_id: int
    duration_seconds: int = Field(..., gt=0)


class SessionUpdate(BaseModel):
    session_name: Optional[str] = Field(None, min_length=1, max_length=100)
    duration_seconds: Optional[int] = Field(None, gt=0)


class SessionResponse(BaseModel):
    session_id: int
    session_name: str
    map_id: int
    duration_seconds: int
    created_at: datetime
    map_name: Optional[str] = None


class SessionFireCreate(BaseModel):
    session_id: int
    fire_time_seconds: int = Field(..., ge=0)
    fire_level: int = Field(..., ge=1)
    fire_spread: int = Field(..., ge=0)
    fire_spread_time: int = Field(..., ge=0)
    coord_x: int = Field(..., ge=0)
    coord_y: int = Field(..., ge=0)


class SessionFireClickCreate(BaseModel):
    session_id: int
    fire_time_seconds: int = Field(..., ge=0)
    fire_level: int = Field(..., ge=1)
    fire_spread: int = Field(..., ge=0)
    fire_spread_time: int = Field(..., ge=0)
    cell_id: int


class SessionFireResponse(BaseModel):
    session_fire_id: int
    session_id: int
    fire_time_seconds: int
    fire_level: int
    fire_spread: int
    fire_spread_time: int
    cell_index: int
    coord_x: int
    coord_y: int
    created_at: datetime


class TrainingStartRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    role_id: int
    map_id: int
    session_id: Optional[int] = None
    device_ids: List[int]
    algorithm: int = Field(..., ge=1, le=5)


class TrainingFinishRequest(BaseModel):
    training_run_id: str
    score: int = 0


class Algorithm3StartRequest(BaseModel):
    """Body khi bắt đầu realtime cho thuật toán 3 (gửi từ trang training-live-algorithm3).

    campaign_id: chọn model transformer (map_{map_id}/campaign_{campaign_id}).
    start_x/start_y: vị trí khởi tạo ESKF (mặc định = điểm tập kết / tâm map nếu None).
    offset_angle_bno: bù lệch gắn cảm biến BNO của THIẾT BỊ (mặc định = config PDR).
    """
    campaign_id: int
    start_x: Optional[float] = None
    start_y: Optional[float] = None
    offset_angle_bno: Optional[float] = None
    assembly_x: Optional[int] = None     # ô điểm tập kết (góc dưới-trái) để nạp nước
    assembly_y: Optional[int] = None
    admin_enabled: bool = False          # bật thiết bị ADMIN ảo (hex 0xad)
    save_history: bool = False           # lưu quỹ đạo CSV vào history_run/ khi kết thúc phiên


class Algorithm3AdminState(BaseModel):
    """Trạng thái thiết bị ADMIN ảo do người điều khiển trên màn hình server đẩy lên."""
    x: float
    y: float
    yaw_map: float = 0.0
    valve_open: float = 0.0
    valve_mode: float = 0.0
    visible: bool = True


class UWBStartRequest(BaseModel):
    """Body bắt đầu realtime cho thuật toán UWB (2 loosely-LM / 5 tightly-EKF).

    KHÔNG cần campaign_id/offset_angle_bno (UWB định vị bằng range, không model/PDR).
    start_x/start_y: vị trí khởi tạo bộ lọc (mặc định = điểm tập kết / tâm map nếu None).
    Trạng thái ADMIN ảo dùng chung models.Algorithm3AdminState.
    """
    start_x: Optional[float] = None
    start_y: Optional[float] = None
    assembly_x: Optional[int] = None     # ô điểm tập kết (góc dưới-trái) để nạp nước
    assembly_y: Optional[int] = None
    admin_enabled: bool = False          # bật thiết bị ADMIN ảo (hex 0xad)
    save_history: bool = False           # lưu quỹ đạo CSV vào history_run/ khi kết thúc phiên


class SessionHistoryCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    device_id: int
    session_id: int
    completion_seconds: int = Field(..., ge=0)
    score: int = 0


class SessionHistoryResponse(BaseModel):
    session_history_id: int
    username: str
    device_id: int
    session_id: int
    completion_seconds: int
    score: int
    completed_at: datetime
    device_name: Optional[str] = None
    session_name: Optional[str] = None


# ============================================================
# Statistics Models
# ============================================================

class CellDataStats(BaseModel):
    """Model for cell data collection statistics"""
    cell_id: int
    cell_index: int
    coord_x: int
    coord_y: int
    collected_samples: int
    target_samples: int


# ============================================================
# Response Models
# ============================================================

class SuccessResponse(BaseModel):
    """Generic success response"""
    success: bool = True
    message: str
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    """Generic error response"""
    success: bool = False
    message: str
    detail: Optional[str] = None
