from sqlalchemy import Column, Integer, String, Float, Boolean, JSON, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String(100))

class DeviceRSSI(Base):
    __tablename__ = "device_rssi"
    device_id = Column(Integer, primary_key=True, index=True)
    device_name = Column(String(50), unique=True, index=True)
    device_hex_id = Column(String(10))

class DeviceUWB(Base):
    __tablename__ = "device_uwb"
    device_id = Column(Integer, primary_key=True, index=True)
    device_name = Column(String(50), unique=True, index=True)
    device_hex_id = Column(String(10))

class RSSIMapInfo(Base):
    __tablename__ = "rssi_map_info"

    map_info_id = Column(Integer, primary_key=True)
    total_units = Column(Integer)
    area_of_one_unit = Column(Float)
    north_offset = Column(Integer, default=90)
    walkable_area = Column(Integer)
    router_number = Column(Integer)
    router_location = Column(JSON, default=[])
    rows = Column(Integer)
    cols = Column(Integer)
    blocked_cells = Column(JSON, default=[])

    # Thuộc tính Cascade để xóa các bảng con phụ thuộc
    rssi_data = relationship(
        "RSSIForTraining", 
        back_populates="map_reference", 
        cascade="all, delete-orphan"
    )

class UwbMapInfo(Base):
    __tablename__ = "uwb_map_info"

    map_info_id = Column(Integer, primary_key=True)
    total_units = Column(Integer)
    area_of_one_unit = Column(Float)
    north_offset = Column(Integer, default=90)
    walkable_area = Column(Integer)
    beacon_number = Column(Integer)
    beacon_location = Column(JSON, default={})
    rows = Column(Integer)
    cols = Column(Integer)
    blocked_cells = Column(JSON, default=[])
  
class UserDataRSSI(Base):
    __tablename__ = "user_data_rssi"

    user_data_rssi_id = Column(Integer, primary_key=True)
    rssi_wifi_1 = Column(Float)
    rssi_wifi_2 = Column(Float)
    rssi_wifi_3 = Column(Float)
    rssi_wifi_4 = Column(Float)
    rssi_ble_1 = Column(Float)
    rssi_ble_2 = Column(Float)  
    rssi_ble_3 = Column(Float)
    rssi_ble_4 = Column(Float)
    accx = Column(Float)
    accy = Column(Float)
    accz = Column(Float)
    magx = Column(Float)
    magy = Column(Float)
    magz = Column(Float)
    gyrox = Column(Float)
    gyroy = Column(Float)
    gyroz = Column(Float)
    pitch = Column(Float)
    roll = Column(Float)
    yaw = Column(Float)
    valve_open = Column(Float)
    valve_mode = Column(Float)
    btn_a = Column(Integer)
    btn_b = Column(Integer)
    btn_c = Column(Integer)

class UserDataUWB(Base):
    __tablename__ = "user_data_uwb"

    user_data_uwb_id = Column(Integer, primary_key=True)
    accx = Column(Float)
    accy = Column(Float)
    accz = Column(Float)
    magx = Column(Float)
    magy = Column(Float)
    magz = Column(Float)
    gyrox = Column(Float)
    gyroy = Column(Float)
    gyroz = Column(Float)
    pitch = Column(Float)
    roll = Column(Float)
    yaw = Column(Float)
    valve_open = Column(Float)
    valve_mode = Column(Float)
    btn_a = Column(Integer)
    btn_b = Column(Integer)
    btn_c = Column(Integer)

class RSSIForTraining(Base):
    __tablename__ = "rssi_for_training"

    rssi_for_training_id = Column(Integer, primary_key=True)
    map_info_id = Column(Integer, ForeignKey("rssi_map_info.map_info_id"))
    coord_x = Column(Float)
    coord_y = Column(Float)
    rssi_wifi_1 = Column(Float)
    rssi_wifi_2 = Column(Float)
    rssi_wifi_3 = Column(Float)
    rssi_wifi_4 = Column(Float)
    rssi_ble_1 = Column(Float)
    rssi_ble_2 = Column(Float)
    rssi_ble_3 = Column(Float)
    rssi_ble_4 = Column(Float)
    magnetic_field_y = Column(Float)
    magnetic_field_z = Column(Float)
    samples = Column(Integer, default=1)

    map_reference = relationship("RSSIMapInfo", back_populates="rssi_data")

class Scenario(Base):
    __tablename__ = "scenarios"
    scenario_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    map_info_id = Column(Integer, index=True)
    map_type = Column(String(50))
    scenario_name = Column(String(255))

    fires = relationship("ScenarioFire", back_populates="scenario", cascade="all, delete-orphan")
    histories = relationship("TrainingHistory", back_populates="scenario", cascade="all, delete-orphan")

class ScenarioFire(Base):
    __tablename__ = "scenario_fires"
    fire_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.scenario_id", ondelete="CASCADE"))
    coord_x = Column(Float)
    coord_y = Column(Float)
    level = Column(Integer) 
    delay_time = Column(Integer)
    is_spreading = Column(Boolean, default=False) 

    scenario = relationship("Scenario", back_populates="fires")

class TrainingHistory(Base):
    __tablename__ = "training_history"
    history_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    trainee_name = Column(String(100))
    scenario_id = Column(Integer, ForeignKey("scenarios.scenario_id", ondelete="CASCADE"))
    device_hex_id = Column(String(100))
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    time_elapsed = Column(Integer)
    score = Column(Integer)

    scenario = relationship("Scenario", back_populates="histories")