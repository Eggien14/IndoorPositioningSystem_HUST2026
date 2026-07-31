# ============================================================
# CONFIG — chỉnh 2 dòng này trước khi chạy
# ============================================================
MAP_ID      = 17
CAMPAIGN_ID = 18
# ============================================================

import csv
import os
import sys
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / '.env')

DB_CONFIG = {
    'host':     os.getenv('DB_HOST', 'localhost'),
    'port':     int(os.getenv('DB_PORT', 3306)),
    'user':     os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'indoor_positioning_db'),
    'charset':  'utf8mb4',
}

QUERY = """
SELECT
    fd.fingerprint_id,
    fd.campaign_id,
    fd.cell_id,
    mc.cell_index,
    mc.coord_x,
    mc.coord_y,
    fd.wifi_rssi_1, fd.wifi_rssi_2, fd.wifi_rssi_3, fd.wifi_rssi_4,
    fd.ble_rssi_1,  fd.ble_rssi_2,  fd.ble_rssi_3,  fd.ble_rssi_4,
    fd.acc_x,  fd.acc_y,  fd.acc_z,
    fd.gyro_x, fd.gyro_y, fd.gyro_z,
    fd.mag_x,  fd.mag_y,  fd.mag_z,
    fd.yaw, fd.roll, fd.pitch,
    fd.collected_at
FROM fingerprint_data fd
JOIN map_cells mc         ON fd.cell_id      = mc.cell_id
JOIN measurement_campaigns camp ON fd.campaign_id = camp.campaign_id
WHERE camp.map_id    = %s
  AND fd.campaign_id = %s
ORDER BY mc.cell_index, fd.fingerprint_id
"""


def main() -> None:
    output_dir = Path(__file__).resolve().parent / 'result'
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f'map_{MAP_ID}_campaign_{CAMPAIGN_ID}_fingerprints_data.csv'

    print(f'Connecting to {DB_CONFIG["host"]}:{DB_CONFIG["port"]} ...')
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    print(f'Querying map_id={MAP_ID}, campaign_id={CAMPAIGN_ID} ...')
    cursor.execute(QUERY, (MAP_ID, CAMPAIGN_ID))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        print('Không tìm thấy dữ liệu. Kiểm tra lại MAP_ID và CAMPAIGN_ID.')
        sys.exit(1)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f'Xong. {len(rows):,} dòng đã xuất ra:')
    print(f'  {output_path}')


if __name__ == '__main__':
    main()
