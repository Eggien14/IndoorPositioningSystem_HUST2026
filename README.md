# Indoor Positioning System for Virtual Firefighting Training (HUST)

This repository holds the hardware, firmware and software of two projects at the iPAC Lab, Hanoi University of Science and Technology (HUST):

- **Bachelor's thesis (2025-2026):** *Design of a virtual firefighting training support system using indoor positioning techniques* ("Thiết kế hệ thống hỗ trợ huấn luyện chữa cháy trong môi trường ảo ứng dụng các kỹ thuật định vị trong nhà"). Each trainee is tracked indoors along two paths: UWB for high precision, and Wi-Fi/BLE fingerprints fused with an IMU for wide coverage. The server runs the fire scenario, the extinguishing and the scoring. Best thesis of the committee, grade A+.
- **Project 2 (2024-2025):** indoor positioning from Wi-Fi RSSI and the geomagnetic field, with a custom data collection module (ESP32, Raspberry Pi Pico, BNO055 IMU).

## Results

| Method | Mean error |
|---|---|
| Wi-Fi, BLE and IMU fusion (thesis) | 0.42 m |
| UWB (thesis) | 0.38 m |
| CNN on Wi-Fi and geomagnetic fingerprints with Kalman-based dead reckoning (Project 2) | 0.537 m |

## Repository map

| Folder | Contents |
|---|---|
| `Bachelor's Thesis/` | Final thesis (PDF) and defence slides |
| `Software/Server_main/` | Main server of the thesis: FastAPI, MySQL, MQTT, Jinja2 web pages. Map and beacon management, fingerprint collection, real-time positioning, fire-spread simulation and scoring |
| `Software/Server_NXS/` | Earlier server prototype (FastAPI, SQLAlchemy, React) for RSSI and UWB positioning |
| `Firmware/ESP32_main/` | Tag firmware (ESP32, PlatformIO): Wi-Fi/BLE RSSI from the scanner MCU over UART, BNO055 IMU, LCD, MQTT |
| `Firmware/esp32_scanwifi/`, `Firmware/esp32_scanble/`, `Firmware/esp32_beaconble/` | Wi-Fi and BLE scanners and BLE beacons (ESP32) |
| `Firmware/UWB_WSN/` | UWB master beacon, slave beacons and tag (STM32F103 with DW1000, STM32CubeIDE), with a TDMA ranging schedule so several tags can range without collisions |
| `Firmware/UWB-centralMCU-Tag/` | ESP32 central MCU of the UWB tag, forwards ranging data over MQTT |
| `Firmware/Dw1000 - Doc & Library/` | DW1000 documents and driver library |
| `Hardware/` | Altium projects: UWB beacon (`PCB_Project_UWB`), UWB tag, UWB kit and the RSSI data collection tag (`RSSI_Tag`) |

## Main server: positioning methods

The server (`Software/Server_main/`) runs several positioning methods side by side and lets each map choose one:

- Algorithm 1: CNN on RSSI fingerprints combined with pedestrian dead reckoning (PDR)
- Algorithm 2: UWB trilateration with a robust Levenberg-Marquardt solver (loosely coupled)
- Algorithm 3: Transformer on Wi-Fi/BLE RSSI fingerprints fused with PDR in an error-state Kalman filter (ESKF)
- Algorithm 5: UWB trilateration with a tightly coupled extended Kalman filter (EKF)

The developer documentation is in Vietnamese, starting at [`Software/Server_main/READ_ME/READ_ME_main.md`](Software/Server_main/READ_ME/READ_ME_main.md): environment and `.env` setup (`READ_ME/Started/Env.md`), MQTT topics, database schema, API and algorithms.

## Quick start (main server)

Requirements: Windows, Python 3.12, MySQL 8 and an MQTT broker (for example Mosquitto) for live data.

```powershell
cd Software\Server_main
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
# create .env with your MySQL settings (DB_HOST, DB_USER, DB_PASSWORD, DB_NAME), see READ_ME/Started/Env.md
.\scripts\start_server.ps1        # http://127.0.0.1:8000
```

Passwords are not stored in the repository: the servers read them from `.env` or environment variables (`DATABASE_URL` for `Server_NXS`).

## Firmware build

- ESP32 projects: open the folder in VS Code with PlatformIO, then build and upload.
- UWB projects (`Firmware/UWB_WSN/`): open in STM32CubeIDE (STM32F103C8), build and flash with an ST-Link.

## Publications

1. P. X. Hieu, N. T. Kien (equal contribution), V. Q. N. Hai, N. V. Hung, N. X. Son and H. D. Chinh, "Indoor Positioning via Wi-Fi and Geomagnetic field using CNN and Kalman-based PDR refinement," *Proc. 2025 Asia Meeting on Environment and Electrical Engineering (EEE-AM)*, Hanoi, 2025, pp. 1-6. doi: [10.1109/EEE-AM66675.2025.11473930](https://doi.org/10.1109/EEE-AM66675.2025.11473930)
2. N. T. Kien, N. V. Hung, V. Q. N. Hai, N. X. Son and H. D. Chinh, "An Improved Indoor Positioning System based on Wi-Fi, BLE, and IMU Fusion using Attention Mechanism," *Proc. 2026 8th Int. Conf. on Green Technology and Sustainable Development (GTSD)*, Ho Chi Minh City, 2026, pp. 614-619. doi: [10.1109/GTSD70918.2026.11722387](https://doi.org/10.1109/GTSD70918.2026.11722387)

## Team

Thesis: team of 5, led by Nguyen Trung Kien ([@Eggien14](https://github.com/Eggien14)), who built the main server and co-wrote the fingerprint collection firmware and the UWB TDMA ranging scheduler. Project 2: team of 7, led by Nguyen Trung Kien, who built the data collection hardware and firmware.
