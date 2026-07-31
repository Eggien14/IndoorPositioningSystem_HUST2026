-- ============================================================
-- Indoor Positioning System - Database Initialization Script
-- ============================================================
-- This script creates the database schema for the IPS fingerprinting system
-- It includes map management, cell grid system, measurement campaigns, and sensor data storage

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS indoor_positioning_db 
    DEFAULT CHARACTER SET utf8mb4 
    COLLATE utf8mb4_unicode_ci;

USE indoor_positioning_db;

-- Track idempotent schema migrations that must not run more than once.
CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_id VARCHAR(100) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Tracks one-way schema migrations applied by init.sql';

-- ============================================================
-- Table 1: maps (Store map overview information)
-- ============================================================
CREATE TABLE IF NOT EXISTS maps (
    map_id INT AUTO_INCREMENT PRIMARY KEY,
    map_name VARCHAR(100) NOT NULL,
    length_x INT NOT NULL COMMENT 'Number of cells along X-axis (Ox)',
    width_y INT NOT NULL COMMENT 'Number of cells along Y-axis (Oy)',
    offset_angles DECIMAL(6,2) NOT NULL DEFAULT 0.00 COMMENT 'Map clockwise offset angle from true north (degrees)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_map_name (map_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Stores overview information of indoor maps';

ALTER TABLE maps
    ADD COLUMN IF NOT EXISTS offset_angles DECIMAL(6,2) NOT NULL DEFAULT 0.00 COMMENT 'Map clockwise offset angle from true north (degrees)';

-- ============================================================
-- Table 2: map_cells (Store detailed information of each cell)
-- ============================================================
CREATE TABLE IF NOT EXISTS map_cells (
    cell_id INT AUTO_INCREMENT PRIMARY KEY,
    map_id INT NOT NULL,
    cell_index INT NOT NULL COMMENT 'Sequential number of cell in the map (1 to length_x * width_y)',
    coord_x INT NOT NULL COMMENT 'X coordinate of bottom-left corner',
    coord_y INT NOT NULL COMMENT 'Y coordinate of bottom-left corner',
    is_passable TINYINT(1) DEFAULT 1 COMMENT '1 = passable, 0 = blocked',
    
    -- Foreign key constraint
    CONSTRAINT fk_cell_map FOREIGN KEY (map_id) 
        REFERENCES maps(map_id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE,
    
    -- Unique constraints to prevent duplicates
    CONSTRAINT uk_map_cell_index UNIQUE (map_id, cell_index),
    CONSTRAINT uk_map_coordinates UNIQUE (map_id, coord_x, coord_y),
    
    -- Indexes for performance
    INDEX idx_map_id (map_id),
    INDEX idx_coordinates (coord_x, coord_y)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Stores grid cell details for each map (1m x 1m cells in Cartesian coordinates)';

-- ============================================================
-- Table 3: measurement_campaigns (Store data collection campaigns)
-- ============================================================
CREATE TABLE IF NOT EXISTS measurement_campaigns (
    campaign_id INT AUTO_INCREMENT PRIMARY KEY,
    map_id INT NOT NULL,
    sample_number INT NOT NULL DEFAULT 0 COMMENT 'Target number of samples per cell',
    campaign_name VARCHAR(100) NULL COMMENT 'Optional name/description for the campaign',
    measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint
    CONSTRAINT fk_campaign_map FOREIGN KEY (map_id) 
        REFERENCES maps(map_id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE,
    
    -- Indexes
    INDEX idx_campaign_map (map_id),
    INDEX idx_measured_at (measured_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Manages measurement campaigns for offline fingerprinting data collection';

-- ============================================================
-- Table 4: fingerprint_data (Store actual sensor measurements)
-- ============================================================
CREATE TABLE IF NOT EXISTS fingerprint_data (
    fingerprint_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    campaign_id INT NOT NULL,
    cell_id INT NOT NULL,
    
    -- WiFi RSSI values (4 access points)
    wifi_rssi_1 INT NULL COMMENT 'WiFi AP 1 signal strength (dBm)',
    wifi_rssi_2 INT NULL COMMENT 'WiFi AP 2 signal strength (dBm)',
    wifi_rssi_3 INT NULL COMMENT 'WiFi AP 3 signal strength (dBm)',
    wifi_rssi_4 INT NULL COMMENT 'WiFi AP 4 signal strength (dBm)',
    
    -- Bluetooth Low Energy RSSI values (4 beacons)
    ble_rssi_1 INT NULL COMMENT 'BLE beacon 1 signal strength (dBm)',
    ble_rssi_2 INT NULL COMMENT 'BLE beacon 2 signal strength (dBm)',
    ble_rssi_3 INT NULL COMMENT 'BLE beacon 3 signal strength (dBm)',
    ble_rssi_4 INT NULL COMMENT 'BLE beacon 4 signal strength (dBm)',
    
    -- Accelerometer data (3 axes)
    acc_x FLOAT NULL COMMENT 'Accelerometer X-axis (m/s²)',
    acc_y FLOAT NULL COMMENT 'Accelerometer Y-axis (m/s²)',
    acc_z FLOAT NULL COMMENT 'Accelerometer Z-axis (m/s²)',
    
    -- Gyroscope data (3 axes)
    gyro_x FLOAT NULL COMMENT 'Gyroscope X-axis (rad/s)',
    gyro_y FLOAT NULL COMMENT 'Gyroscope Y-axis (rad/s)',
    gyro_z FLOAT NULL COMMENT 'Gyroscope Z-axis (rad/s)',
    
    -- Magnetometer/Geomagnetic data (3 axes)
    mag_x FLOAT NULL COMMENT 'Magnetometer X-axis (μT)',
    mag_y FLOAT NULL COMMENT 'Magnetometer Y-axis (μT)',
    mag_z FLOAT NULL COMMENT 'Magnetometer Z-axis (μT)',
    
    -- Orientation data (Euler angles)
    yaw FLOAT NULL COMMENT 'Heading/Yaw angle (degrees)',
    roll FLOAT NULL COMMENT 'Roll angle (degrees)',
    pitch FLOAT NULL COMMENT 'Pitch angle (degrees)',
    
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_fingerprint_campaign FOREIGN KEY (campaign_id) 
        REFERENCES measurement_campaigns(campaign_id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE,
    CONSTRAINT fk_fingerprint_cell FOREIGN KEY (cell_id) 
        REFERENCES map_cells(cell_id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE,
    
    -- Indexes for performance
    INDEX idx_campaign_cell (campaign_id, cell_id),
    INDEX idx_collected_at (collected_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Stores raw sensor measurements for fingerprinting algorithm training';

-- Migration: original parser stored payload fields 18/19/20 as roll/pitch/yaw,
-- but the real MQTT order is heading-yaw/roll/pitch. Rotate column names only;
-- do not update stored values.
SET @orientation_migration = '20260429_fingerprint_orientation_yaw_roll_pitch';
SET @orientation_migration_done = (
    SELECT COUNT(*)
    FROM schema_migrations
    WHERE migration_id = @orientation_migration
);
SET @orientation_order = (
    SELECT GROUP_CONCAT(COLUMN_NAME ORDER BY ORDINAL_POSITION SEPARATOR ',')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'fingerprint_data'
      AND COLUMN_NAME IN ('yaw', 'roll', 'pitch')
);
SET @needs_orientation_rotation = (
    @orientation_migration_done = 0
    AND @orientation_order = 'roll,pitch,yaw'
);

SET @sql = IF(
    @needs_orientation_rotation,
    'ALTER TABLE fingerprint_data CHANGE COLUMN roll orientation_yaw_tmp FLOAT NULL COMMENT ''Heading/Yaw angle (degrees)'' AFTER mag_z',
    'SELECT 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    @needs_orientation_rotation,
    'ALTER TABLE fingerprint_data CHANGE COLUMN pitch roll FLOAT NULL COMMENT ''Roll angle (degrees)'' AFTER orientation_yaw_tmp',
    'SELECT 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    @needs_orientation_rotation,
    'ALTER TABLE fingerprint_data CHANGE COLUMN yaw pitch FLOAT NULL COMMENT ''Pitch angle (degrees)'' AFTER roll',
    'SELECT 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    @needs_orientation_rotation,
    'ALTER TABLE fingerprint_data CHANGE COLUMN orientation_yaw_tmp yaw FLOAT NULL COMMENT ''Heading/Yaw angle (degrees)'' AFTER mag_z',
    'SELECT 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

INSERT INTO schema_migrations (migration_id)
SELECT @orientation_migration
WHERE @orientation_migration_done = 0
  AND @orientation_order IN ('roll,pitch,yaw', 'yaw,roll,pitch')
ON DUPLICATE KEY UPDATE applied_at = applied_at;

-- ============================================================
-- Table 5: account (Store user login and role)
-- role_id: 1 = admin, 2 = trainer, 3 = trainee
-- ============================================================
CREATE TABLE IF NOT EXISTS account (
    username VARCHAR(50) PRIMARY KEY,
    password VARCHAR(255) NOT NULL,
    role_id TINYINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_account_role CHECK (role_id IN (1, 2, 3)),
    INDEX idx_account_role (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Stores user login credentials and authorization roles';

INSERT INTO account (username, password, role_id)
VALUES
    ('admin', 'admin', 1),
    ('trainer', 'trainer', 2),
    ('trainee', 'trainee', 3)
ON DUPLICATE KEY UPDATE
    password = VALUES(password),
    role_id = VALUES(role_id);

-- ============================================================
-- Table 6: device (Store device registry)
-- ============================================================
DROP TABLE IF EXISTS session_history;
DROP TABLE IF EXISTS device;

CREATE TABLE device (
    device_id INT AUTO_INCREMENT PRIMARY KEY,
    device_name VARCHAR(100) NOT NULL,
    device_hex_id VARCHAR(32) NOT NULL COMMENT 'Printed device identifier, ex: 0xAB',
    water_capacity INT NOT NULL DEFAULT 100 COMMENT 'Water tank capacity: -1 = infinite; >=0 = finite (same units as sim WATER_MAX, default 100)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_device_name (device_name),
    UNIQUE KEY uk_device_hex_id (device_hex_id),
    CONSTRAINT ck_device_water_capacity CHECK (water_capacity >= -1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Stores available devices with physical hex IDs';

-- ============================================================
-- Table 6.1: map_beacon (Store beacon configuration per map)
-- beacon_type: 1=wifi, 2=ble, 3=uwb_slave, 4=uwb_master
-- ============================================================
CREATE TABLE IF NOT EXISTS map_beacon (
    beacon_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    map_id INT NOT NULL,
    beacon_hex_id VARCHAR(32) NOT NULL,
    beacon_type TINYINT NOT NULL,
    coord_x DECIMAL(10,2) NOT NULL,
    coord_y DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_map_beacon_map FOREIGN KEY (map_id)
        REFERENCES maps(map_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT ck_map_beacon_type CHECK (beacon_type IN (1, 2, 3, 4)),
    UNIQUE KEY uk_map_beacon_hex (map_id, beacon_hex_id),
    INDEX idx_map_beacon_map (map_id),
    INDEX idx_map_beacon_type (map_id, beacon_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Stores beacon identities, types, and coordinates for each map';

-- ============================================================
-- Table 6.2: map_algorithm (Store available algorithms per map)
-- algorithm: 1=fingerprint CNN-PDR, 2=trilateration LM (loosely-coupled),
--            3=fingerprints Transformer ESKF,
--            4=fingerprints Multi modal cross attention,
--            5=trilateration tightly-coupled EKF
-- ============================================================
CREATE TABLE IF NOT EXISTS map_algorithm (
    map_id INT NOT NULL,
    algorithm TINYINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (map_id, algorithm),
    CONSTRAINT fk_map_algorithm_map FOREIGN KEY (map_id)
        REFERENCES maps(map_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT ck_map_algorithm_value CHECK (algorithm IN (1, 2, 3, 4, 5)),
    INDEX idx_map_algorithm_algorithm (algorithm)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Stores enabled algorithms for each map';

-- ============================================================
-- Table 7: session (Store training sessions)
-- ============================================================
CREATE TABLE IF NOT EXISTS `session` (
    session_id INT AUTO_INCREMENT PRIMARY KEY,
    session_name VARCHAR(100) NOT NULL,
    map_id INT NOT NULL,
    duration_seconds INT NOT NULL COMMENT 'Training duration in seconds',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_session_map FOREIGN KEY (map_id)
        REFERENCES maps(map_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    INDEX idx_session_map (map_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Stores training sessions linked to maps';

-- ============================================================
-- Table 8: session_fire (Store fire timeline for each session)
-- ============================================================
CREATE TABLE IF NOT EXISTS session_fire (
    session_fire_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    fire_time_seconds INT NOT NULL COMMENT 'Time offset from session start',
    fire_level INT NOT NULL,
    fire_spread INT NOT NULL DEFAULT 0 COMMENT 'Fire spread rate (cells per spread step)',
    fire_spread_time INT NOT NULL DEFAULT 0 COMMENT 'Interval between spread steps (seconds)',
    cell_index INT NOT NULL,
    coord_x INT NOT NULL,
    coord_y INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_session_fire_session FOREIGN KEY (session_id)
        REFERENCES `session`(session_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    INDEX idx_session_fire_session (session_id),
    INDEX idx_session_fire_timeline (session_id, fire_time_seconds)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Stores fire events and timeline for training sessions';

-- Migration: add fire_spread and fire_spread_time to existing session_fire tables
SET @has_fire_spread = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'session_fire' AND COLUMN_NAME = 'fire_spread'
);
SET @sql_fs = IF(@has_fire_spread = 0,
    "ALTER TABLE session_fire ADD COLUMN fire_spread INT NOT NULL DEFAULT 0 COMMENT 'Fire spread rate (cells per spread step)' AFTER fire_level",
    'SELECT 0');
PREPARE stmt FROM @sql_fs; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_fire_spread_time = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'session_fire' AND COLUMN_NAME = 'fire_spread_time'
);
SET @sql_fst = IF(@has_fire_spread_time = 0,
    "ALTER TABLE session_fire ADD COLUMN fire_spread_time INT NOT NULL DEFAULT 0 COMMENT 'Interval between spread steps (seconds)' AFTER fire_spread",
    'SELECT 0');
PREPARE stmt FROM @sql_fst; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ============================================================
-- Table 9: session_history (Store finished session records)
-- ============================================================
CREATE TABLE session_history (
    session_history_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    device_id INT NOT NULL,
    session_id INT NOT NULL,
    completion_seconds INT NOT NULL,
    score INT NOT NULL DEFAULT 0,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_session_history_account FOREIGN KEY (username)
        REFERENCES account(username)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT fk_session_history_device FOREIGN KEY (device_id)
        REFERENCES device(device_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT fk_session_history_session FOREIGN KEY (session_id)
        REFERENCES `session`(session_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    INDEX idx_session_history_user (username),
    INDEX idx_session_history_session (session_id),
    INDEX idx_session_history_completed (completed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Stores completed training session history records';

-- ============================================================
-- Success message
-- ============================================================
SELECT 'Database schema created successfully!' AS Status;
