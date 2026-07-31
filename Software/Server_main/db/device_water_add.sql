-- ============================================================
-- Migration: add `water_capacity` to Table 6 `device`.
--
-- init.sql only runs when building the database the first time;
-- run THIS file once on an EXISTING database (e.g. in MySQL Workbench)
-- to add the per-device water tank capacity column.
--
-- Semantics (matches the simulation logic):
--   water_capacity = -1   -> INFINITE water (never drains, always able to spray)
--   water_capacity >=  0  -> finite tank (drains while spraying, refills at the
--                            assembly point), default 100 (= sim WATER_MAX).
--
-- Safe to re-run: adds the column / CHECK only if missing.
-- Requires MySQL 8.0.16+ (CHECK constraints enforced).
-- HOW TO RUN: open this file and press "Execute all" (Ctrl+Shift+Enter) — it uses
-- prepared statements so it MUST run as a whole script, not line-by-line.
-- ============================================================

USE indoor_positioning_db;

-- 1) Add column `water_capacity` (only if it does not already exist).
SET @has_col = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'indoor_positioning_db'
      AND TABLE_NAME   = 'device'
      AND COLUMN_NAME  = 'water_capacity'
);
SET @sql = IF(@has_col > 0,
    'SELECT 1',
    'ALTER TABLE indoor_positioning_db.device
        ADD COLUMN water_capacity INT NOT NULL DEFAULT 100
        COMMENT ''Water tank capacity: -1 = infinite; >=0 = finite (default 100)''
        AFTER device_hex_id');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2) Add CHECK constraint water_capacity >= -1 (only if it does not already exist).
SET @has_chk = (
    SELECT COUNT(*)
    FROM information_schema.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA   = 'indoor_positioning_db'
      AND TABLE_NAME     = 'device'
      AND CONSTRAINT_NAME = 'ck_device_water_capacity'
      AND CONSTRAINT_TYPE = 'CHECK'
);
SET @sql = IF(@has_chk > 0,
    'SELECT 1',
    'ALTER TABLE indoor_positioning_db.device
        ADD CONSTRAINT ck_device_water_capacity CHECK (water_capacity >= -1)');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3) (Optional examples — uncomment & edit to set special values directly)
-- UPDATE indoor_positioning_db.device SET water_capacity = -1  WHERE device_name = 'D8';   -- infinite
-- UPDATE indoor_positioning_db.device SET water_capacity = 200 WHERE device_id = 3;         -- bigger tank

-- 4) Verify
SELECT device_id, device_name, device_hex_id, water_capacity
FROM indoor_positioning_db.device
ORDER BY device_id;
