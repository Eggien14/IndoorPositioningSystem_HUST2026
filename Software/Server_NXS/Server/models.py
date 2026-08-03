from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class UserSchema(BaseModel):
    id: int | None = None
    username: str
    password: str

class DeviceRSSISchema(BaseModel):
    device_id: int | None = None
    device_name: str
    device_hex_id: str

class DeviceUWBSchema(BaseModel):
    device_id: int | None = None
    device_name: str
    device_hex_id: str

class DeviceRenameSchema(BaseModel):
    device_name: str

class RSSIMapInfoSchema(BaseModel):
    map_info_id: int | None = None
    total_units: int
    area_of_one_unit: float
    north_offset: int
    walkable_area: int
    router_number: int
    router_location: List[str]
    rows: int
    cols: int
    blocked_cells: List[str]

class UwbMapInfoSchema(BaseModel):
    map_info_id: int | None = None
    total_units: int
    area_of_one_unit: float
    north_offset: int
    walkable_area: int
    beacon_number: int
    beacon_location: dict
    rows: int
    cols: int
    blocked_cells: List[str]

class RSSIForTrainingSchema(BaseModel):
    rssi_for_training_id: int | None = None
    map_info_id: int = 0
    coord_x: float = 0.0
    coord_y: float = 0.0
    rssi_wifi_1: float
    rssi_wifi_2: float
    rssi_wifi_3: float
    rssi_wifi_4: float
    rssi_ble_1: float
    rssi_ble_2: float
    rssi_ble_3: float
    rssi_ble_4: float
    magnetic_field_y: float
    magnetic_field_z: float
    samples: int = 1

class BnoVectorSchema(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

class BnoEulerSchema(BaseModel):
    yaw: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0

class BnoSchema(BaseModel):
    acc: BnoVectorSchema = Field(default_factory=BnoVectorSchema)
    gyro: BnoVectorSchema = Field(default_factory=BnoVectorSchema)
    mag: BnoVectorSchema = Field(default_factory=BnoVectorSchema)
    euler: BnoEulerSchema = Field(default_factory=BnoEulerSchema)

class ValveSchema(BaseModel):
    open: float = 0.0
    mode: float = 100.0

class ButtonSchema(BaseModel):
    A: int = 0
    B: int = 0
    C: int = 0

class UwbPayloadSchema(BaseModel):
    bno: BnoSchema = Field(default_factory=BnoSchema)
    valve: ValveSchema = Field(default_factory=ValveSchema)
    button: ButtonSchema = Field(default_factory=ButtonSchema)

class RssiMacSchema(BaseModel):
    mac_1: float = Field(default=-100.0, alias="1")
    mac_2: float = Field(default=-100.0, alias="2")
    mac_3: float = Field(default=-100.0, alias="3")
    mac_4: float = Field(default=-100.0, alias="4")

class RealityPayloadSchema(BaseModel):
    rssi_wifi: RssiMacSchema = Field(default_factory=RssiMacSchema)
    rssi_ble: RssiMacSchema = Field(default_factory=RssiMacSchema)
    bno: BnoSchema = Field(default_factory=BnoSchema)
    valve: ValveSchema = Field(default_factory=ValveSchema)
    button: ButtonSchema = Field(default_factory=ButtonSchema)
        
class TrainingPayloadSchema(BaseModel):
    rssi_wifi: RssiMacSchema = Field(default_factory=RssiMacSchema)
    rssi_ble: RssiMacSchema = Field(default_factory=RssiMacSchema)
    bno: BnoSchema = Field(default_factory=BnoSchema)

class CollectDataRequestSchema(BaseModel):
    map_info_id: int
    coord_x: float
    coord_y: float
    samples: int = 1

class ScenarioFireSchema(BaseModel):
    coord_x: float
    coord_y: float
    level: int
    delay_time: int
    is_spreading: bool = False

class ScenarioSchema(BaseModel):
    map_info_id: int
    map_type: str
    scenario_name: str
    fires: List[ScenarioFireSchema] = []

class TrainingHistorySchema(BaseModel):
    trainee_name: str
    scenario_id: int
    device_hex_id: str
    time_elapsed: int
    score: int