"""
CRUD operations for Indoor Positioning System
"""
from typing import List, Optional, Dict, Any
from backend.database import execute_query, execute_many
from backend.models import (
    MapCreate, CellUpdate, CampaignCreate, FingerprintCreate,
    DeviceCreate, DeviceUpdate, SessionCreate, SessionUpdate,
    SessionHistoryCreate
)


# ============================================================
# Map Operations
# ============================================================

def create_map(map_data: MapCreate) -> int:
    """
    Create a new map and automatically generate all cells
    
    Returns:
        map_id of the newly created map
    """
    # Insert map
    query = """
        INSERT INTO maps (map_name, length_x, width_y, offset_angles)
        VALUES (%s, %s, %s, %s)
    """
    map_id = execute_query(
        query,
        (map_data.map_name, map_data.length_x, map_data.width_y, map_data.offset_angles)
    )
    
    # Generate cells
    cells = []
    cell_index = 1
    for y in range(map_data.width_y):
        for x in range(map_data.length_x):
            cells.append((map_id, cell_index, x, y, 1))  # All cells passable by default
            cell_index += 1
    
    # Batch insert cells
    cell_query = """
        INSERT INTO map_cells (map_id, cell_index, coord_x, coord_y, is_passable)
        VALUES (%s, %s, %s, %s, %s)
    """
    execute_many(cell_query, cells)
    
    return map_id


def get_all_maps() -> List[Dict[str, Any]]:
    """Get all maps"""
    query = "SELECT * FROM maps ORDER BY created_at DESC"
    return execute_query(query, fetch=True)


def get_map_by_id(map_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific map by ID"""
    query = "SELECT * FROM maps WHERE map_id = %s"
    return execute_query(query, (map_id,), fetch=True, fetch_one=True)


def delete_map(map_id: int) -> int:
    """
    Delete a map (cascade deletes all related data)
    
    Returns:
        Number of affected rows
    """
    query = "DELETE FROM maps WHERE map_id = %s"
    return execute_query(query, (map_id,))


def update_map_offset_angles(map_id: int, offset_angles: float) -> int:
    query = "UPDATE maps SET offset_angles = %s WHERE map_id = %s"
    return execute_query(query, (offset_angles, map_id))


# ============================================================
# Map Cell Operations
# ============================================================

def get_map_cells(map_id: int) -> List[Dict[str, Any]]:
    """Get all cells for a specific map"""
    query = """
        SELECT * FROM map_cells 
        WHERE map_id = %s 
        ORDER BY coord_y, coord_x
    """
    return execute_query(query, (map_id,), fetch=True)


def get_cell_by_id(cell_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific cell by ID"""
    query = "SELECT * FROM map_cells WHERE cell_id = %s"
    return execute_query(query, (cell_id,), fetch=True, fetch_one=True)


def update_cell(cell_id: int, cell_index: Optional[int] = None, is_passable: Optional[int] = None) -> int:
    """Update a cell's properties"""
    updates = []
    params = []
    
    if cell_index is not None:
        updates.append("cell_index = %s")
        params.append(cell_index)
    
    if is_passable is not None:
        updates.append("is_passable = %s")
        params.append(is_passable)
    
    if not updates:
        return 0
    
    params.append(cell_id)
    query = f"UPDATE map_cells SET {', '.join(updates)} WHERE cell_id = %s"
    return execute_query(query, tuple(params))


def batch_update_cells(cells: List[CellUpdate]) -> int:
    """Batch update multiple cells"""
    total_updated = 0
    for cell in cells:
        updated = update_cell(
            cell.cell_id,
            cell.cell_index,
            cell.is_passable
        )
        total_updated += updated
    return total_updated


def check_duplicate_cell_index(map_id: int, cell_index: int, exclude_cell_id: Optional[int] = None) -> bool:
    """Check if a cell_index already exists in the map"""
    query = """
        SELECT COUNT(*) as count FROM map_cells 
        WHERE map_id = %s AND cell_index = %s
    """
    params = [map_id, cell_index]
    
    if exclude_cell_id:
        query += " AND cell_id != %s"
        params.append(exclude_cell_id)
    
    result = execute_query(query, tuple(params), fetch=True, fetch_one=True)
    return result['count'] > 0


# ============================================================
# Campaign Operations
# ============================================================

def create_campaign(campaign_data: CampaignCreate) -> int:
    """Create a new measurement campaign"""
    query = """
        INSERT INTO measurement_campaigns (map_id, sample_number, campaign_name)
        VALUES (%s, %s, %s)
    """
    return execute_query(
        query,
        (campaign_data.map_id, campaign_data.sample_number, campaign_data.campaign_name)
    )


def get_campaigns_by_map(map_id: int) -> List[Dict[str, Any]]:
    """Get all campaigns for a specific map"""
    query = """
        SELECT * FROM measurement_campaigns 
        WHERE map_id = %s 
        ORDER BY measured_at DESC
    """
    return execute_query(query, (map_id,), fetch=True)


def get_campaign_by_id(campaign_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific campaign by ID"""
    query = "SELECT * FROM measurement_campaigns WHERE campaign_id = %s"
    return execute_query(query, (campaign_id,), fetch=True, fetch_one=True)


def delete_campaign(campaign_id: int) -> int:
    """
    Delete a campaign (cascade deletes all fingerprint data)
    
    Returns:
        Number of affected rows
    """
    query = "DELETE FROM measurement_campaigns WHERE campaign_id = %s"
    return execute_query(query, (campaign_id,))


# ============================================================
# Fingerprint Data Operations
# ============================================================

def create_fingerprint(fingerprint_data: FingerprintCreate) -> int:
    """Create a new fingerprint data record"""
    query = """
        INSERT INTO fingerprint_data (
            campaign_id, cell_id,
            wifi_rssi_1, wifi_rssi_2, wifi_rssi_3, wifi_rssi_4,
            ble_rssi_1, ble_rssi_2, ble_rssi_3, ble_rssi_4,
            acc_x, acc_y, acc_z,
            gyro_x, gyro_y, gyro_z,
            mag_x, mag_y, mag_z,
            yaw, roll, pitch
        ) VALUES (
            %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s
        )
    """
    return execute_query(query, (
        fingerprint_data.campaign_id, fingerprint_data.cell_id,
        fingerprint_data.wifi_rssi_1, fingerprint_data.wifi_rssi_2,
        fingerprint_data.wifi_rssi_3, fingerprint_data.wifi_rssi_4,
        fingerprint_data.ble_rssi_1, fingerprint_data.ble_rssi_2,
        fingerprint_data.ble_rssi_3, fingerprint_data.ble_rssi_4,
        fingerprint_data.acc_x, fingerprint_data.acc_y, fingerprint_data.acc_z,
        fingerprint_data.gyro_x, fingerprint_data.gyro_y, fingerprint_data.gyro_z,
        fingerprint_data.mag_x, fingerprint_data.mag_y, fingerprint_data.mag_z,
        fingerprint_data.yaw, fingerprint_data.roll, fingerprint_data.pitch
    ))


def get_cell_sample_count(campaign_id: int, cell_id: int) -> int:
    """Get the number of samples collected for a specific cell in a campaign"""
    query = """
        SELECT COUNT(*) as count 
        FROM fingerprint_data 
        WHERE campaign_id = %s AND cell_id = %s
    """
    result = execute_query(query, (campaign_id, cell_id), fetch=True, fetch_one=True)
    return result['count']


def get_cell_fingerprints(campaign_id: int, cell_id: int) -> List[Dict[str, Any]]:
    """Get all collected fingerprint samples for a specific cell in a campaign"""
    query = """
        SELECT 
            fingerprint_id,
            campaign_id,
            cell_id,
            wifi_rssi_1, wifi_rssi_2, wifi_rssi_3, wifi_rssi_4,
            ble_rssi_1, ble_rssi_2, ble_rssi_3, ble_rssi_4,
            acc_x, acc_y, acc_z,
            gyro_x, gyro_y, gyro_z,
            mag_x, mag_y, mag_z,
            yaw, roll, pitch,
            collected_at
        FROM fingerprint_data
        WHERE campaign_id = %s AND cell_id = %s
        ORDER BY collected_at ASC, fingerprint_id ASC
    """
    return execute_query(query, (campaign_id, cell_id), fetch=True)


def delete_cell_fingerprints(campaign_id: int, cell_id: int) -> int:
    """Delete all fingerprint data for a specific cell in a campaign (for overwrite)"""
    query = """
        DELETE FROM fingerprint_data 
        WHERE campaign_id = %s AND cell_id = %s
    """
    return execute_query(query, (campaign_id, cell_id))


def get_campaign_statistics(campaign_id: int) -> List[Dict[str, Any]]:
    """Get data collection statistics for all cells in a campaign"""
    query = """
        SELECT 
            mc.cell_id,
            mc.cell_index,
            mc.coord_x,
            mc.coord_y,
            COUNT(fd.fingerprint_id) as collected_samples,
            camp.sample_number as target_samples
        FROM map_cells mc
        INNER JOIN measurement_campaigns camp ON mc.map_id = camp.map_id
        LEFT JOIN fingerprint_data fd ON mc.cell_id = fd.cell_id AND fd.campaign_id = camp.campaign_id
        WHERE camp.campaign_id = %s
        GROUP BY mc.cell_id, mc.cell_index, mc.coord_x, mc.coord_y, camp.sample_number
        ORDER BY mc.coord_y, mc.coord_x
    """
    return execute_query(query, (campaign_id,), fetch=True)


# ============================================================
# Account Operations
# ============================================================

def get_account_by_username(username: str) -> Optional[Dict[str, Any]]:
    query = "SELECT username, password, role_id, created_at FROM account WHERE username = %s"
    return execute_query(query, (username,), fetch=True, fetch_one=True)


def validate_login(username: str, password: str) -> Optional[Dict[str, Any]]:
    query = """
        SELECT username, role_id
        FROM account
        WHERE username = %s AND password = %s
    """
    return execute_query(query, (username, password), fetch=True, fetch_one=True)


# ============================================================
# Device Operations
# ============================================================

def get_all_devices() -> List[Dict[str, Any]]:
    query = "SELECT * FROM device ORDER BY created_at DESC"
    return execute_query(query, fetch=True)


def get_device_by_id(device_id: int) -> Optional[Dict[str, Any]]:
    query = "SELECT * FROM device WHERE device_id = %s"
    return execute_query(query, (device_id,), fetch=True, fetch_one=True)


def create_device(device_data: DeviceCreate) -> int:
    query = """
        INSERT INTO device (device_name, device_hex_id, water_capacity)
        VALUES (%s, %s, %s)
    """
    return execute_query(
        query,
        (device_data.device_name, device_data.device_hex_id, device_data.water_capacity)
    )


def update_device(device_id: int, device_data: DeviceUpdate) -> int:
    updates = []
    params = []

    if device_data.device_name is not None:
        updates.append("device_name = %s")
        params.append(device_data.device_name)
    if device_data.device_hex_id is not None:
        updates.append("device_hex_id = %s")
        params.append(device_data.device_hex_id)
    if device_data.water_capacity is not None:
        updates.append("water_capacity = %s")
        params.append(device_data.water_capacity)

    if not updates:
        return 0

    params.append(device_id)
    query = f"UPDATE device SET {', '.join(updates)} WHERE device_id = %s"
    return execute_query(query, tuple(params))


def delete_device(device_id: int) -> int:
    query = "DELETE FROM device WHERE device_id = %s"
    return execute_query(query, (device_id,))


# ============================================================
# Map Beacon Operations
# ============================================================

def get_map_beacons(map_id: int) -> List[Dict[str, Any]]:
    query = """
        SELECT *
        FROM map_beacon
        WHERE map_id = %s
        ORDER BY beacon_type, beacon_id
    """
    return execute_query(query, (map_id,), fetch=True)


def get_map_beacon_by_id(beacon_id: int) -> Optional[Dict[str, Any]]:
    query = "SELECT * FROM map_beacon WHERE beacon_id = %s"
    return execute_query(query, (beacon_id,), fetch=True, fetch_one=True)


def create_map_beacon(map_id: int, beacon_hex_id: str, beacon_type: int, coord_x: float, coord_y: float) -> int:
    query = """
        INSERT INTO map_beacon (map_id, beacon_hex_id, beacon_type, coord_x, coord_y)
        VALUES (%s, %s, %s, %s, %s)
    """
    return execute_query(query, (map_id, beacon_hex_id, beacon_type, round(coord_x, 2), round(coord_y, 2)))


def update_map_beacon(
    beacon_id: int,
    beacon_hex_id: Optional[str] = None,
    beacon_type: Optional[int] = None,
    coord_x: Optional[float] = None,
    coord_y: Optional[float] = None,
) -> int:
    updates = []
    params = []

    if beacon_hex_id is not None:
        updates.append("beacon_hex_id = %s")
        params.append(beacon_hex_id)
    if beacon_type is not None:
        updates.append("beacon_type = %s")
        params.append(beacon_type)
    if coord_x is not None:
        updates.append("coord_x = %s")
        params.append(round(coord_x, 2))
    if coord_y is not None:
        updates.append("coord_y = %s")
        params.append(round(coord_y, 2))

    if not updates:
        return 0

    params.append(beacon_id)
    query = f"UPDATE map_beacon SET {', '.join(updates)} WHERE beacon_id = %s"
    return execute_query(query, tuple(params))


def delete_map_beacon(beacon_id: int) -> int:
    query = "DELETE FROM map_beacon WHERE beacon_id = %s"
    return execute_query(query, (beacon_id,))


def count_map_beacons_by_type(map_id: int) -> Dict[int, int]:
    query = """
        SELECT beacon_type, COUNT(*) AS count
        FROM map_beacon
        WHERE map_id = %s
        GROUP BY beacon_type
    """
    rows = execute_query(query, (map_id,), fetch=True)
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for row in rows:
        counts[int(row["beacon_type"])] = int(row["count"])
    return counts


# ============================================================
# Map Algorithm Operations
# ============================================================

def get_map_algorithms(map_id: int) -> List[Dict[str, Any]]:
    query = """
        SELECT *
        FROM map_algorithm
        WHERE map_id = %s
        ORDER BY algorithm
    """
    return execute_query(query, (map_id,), fetch=True)


def replace_map_algorithms(map_id: int, algorithms: List[int]) -> None:
    delete_query = "DELETE FROM map_algorithm WHERE map_id = %s"
    execute_query(delete_query, (map_id,))

    unique_algorithms = sorted(set(algorithms))
    if not unique_algorithms:
        return

    insert_query = """
        INSERT INTO map_algorithm (map_id, algorithm)
        VALUES (%s, %s)
    """
    execute_many(insert_query, [(map_id, algorithm) for algorithm in unique_algorithms])


# ============================================================
# Session Operations
# ============================================================

def get_all_sessions() -> List[Dict[str, Any]]:
    query = """
        SELECT s.*, m.map_name
        FROM `session` s
        INNER JOIN maps m ON s.map_id = m.map_id
        ORDER BY s.created_at DESC
    """
    return execute_query(query, fetch=True)


def get_sessions_by_map(map_id: int) -> List[Dict[str, Any]]:
    query = """
        SELECT s.*, m.map_name
        FROM `session` s
        INNER JOIN maps m ON s.map_id = m.map_id
        WHERE s.map_id = %s
        ORDER BY s.created_at DESC
    """
    return execute_query(query, (map_id,), fetch=True)


def get_session_by_id(session_id: int) -> Optional[Dict[str, Any]]:
    query = """
        SELECT s.*, m.map_name
        FROM `session` s
        INNER JOIN maps m ON s.map_id = m.map_id
        WHERE s.session_id = %s
    """
    return execute_query(query, (session_id,), fetch=True, fetch_one=True)


def create_session(session_data: SessionCreate) -> int:
    query = """
        INSERT INTO `session` (session_name, map_id, duration_seconds)
        VALUES (%s, %s, %s)
    """
    return execute_query(
        query,
        (session_data.session_name, session_data.map_id, session_data.duration_seconds)
    )


def update_session(session_id: int, session_data: SessionUpdate) -> int:
    updates = []
    params = []

    if session_data.session_name is not None:
        updates.append("session_name = %s")
        params.append(session_data.session_name)
    if session_data.duration_seconds is not None:
        updates.append("duration_seconds = %s")
        params.append(session_data.duration_seconds)

    if not updates:
        return 0

    params.append(session_id)
    query = f"UPDATE `session` SET {', '.join(updates)} WHERE session_id = %s"
    return execute_query(query, tuple(params))


def delete_session(session_id: int) -> int:
    query = "DELETE FROM `session` WHERE session_id = %s"
    return execute_query(query, (session_id,))


# ============================================================
# Session Fire Operations
# ============================================================

def create_session_fire(
    session_id: int,
    fire_time_seconds: int,
    fire_level: int,
    fire_spread: int,
    fire_spread_time: int,
    cell_index: int,
    coord_x: int,
    coord_y: int
) -> int:
    query = """
        INSERT INTO session_fire (
            session_id, fire_time_seconds, fire_level, fire_spread, fire_spread_time,
            cell_index, coord_x, coord_y
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    return execute_query(
        query,
        (session_id, fire_time_seconds, fire_level, fire_spread, fire_spread_time,
         cell_index, coord_x, coord_y)
    )


def get_session_fires(session_id: int) -> List[Dict[str, Any]]:
    query = """
        SELECT *
        FROM session_fire
        WHERE session_id = %s
        ORDER BY fire_time_seconds, session_fire_id
    """
    return execute_query(query, (session_id,), fetch=True)


def delete_session_fire(session_fire_id: int) -> int:
    query = "DELETE FROM session_fire WHERE session_fire_id = %s"
    return execute_query(query, (session_fire_id,))


def find_cell_by_map_and_coord(map_id: int, coord_x: int, coord_y: int) -> Optional[Dict[str, Any]]:
    query = """
        SELECT * FROM map_cells
        WHERE map_id = %s AND coord_x = %s AND coord_y = %s
    """
    return execute_query(query, (map_id, coord_x, coord_y), fetch=True, fetch_one=True)


# ============================================================
# Session History Operations
# ============================================================

def create_session_history(history_data: SessionHistoryCreate) -> int:
    query = """
        INSERT INTO session_history (
            username, device_id, session_id, completion_seconds, score
        )
        VALUES (%s, %s, %s, %s, %s)
    """
    return execute_query(
        query,
        (
            history_data.username,
            history_data.device_id,
            history_data.session_id,
            history_data.completion_seconds,
            history_data.score,
        )
    )


def get_all_session_history() -> List[Dict[str, Any]]:
    query = """
        SELECT
            h.*,
            d.device_name,
            s.session_name
        FROM session_history h
        INNER JOIN device d ON h.device_id = d.device_id
        INNER JOIN `session` s ON h.session_id = s.session_id
        ORDER BY h.completed_at DESC
    """
    return execute_query(query, fetch=True)
