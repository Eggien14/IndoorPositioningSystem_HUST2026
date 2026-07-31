# Giao Tiếp MQTT — Danh Sách Topic & Mẫu Tin Nhắn

Tài liệu này là **hợp đồng giao tiếp MQTT** giữa thiết bị (device) và server, dùng cho
cả Dev lẫn AI agent. Mô tả toàn bộ topic và mẫu tin nhắn đã thống nhất.

- Bản gốc đầy đủ nhất (kể cả phần chưa làm): `Source/mqtt_topic.txt` (chỉ tham khảo).
- Tài liệu code phía server: `backend/mqtt_handle/CLAUDE_MQTT.md`.
- Cột **Trạng thái** cho biết phần nào server đã hiện thực:
  ✅ = đã làm · ❌ = chưa làm (định nghĩa sẵn cho tương lai).

> **Cấu hình broker:** `backend/mqtt_client.py` đọc `MQTT_BROKER` (mặc định `localhost`),
> `MQTT_PORT`, `MQTT_KEEPALIVE` từ `.env`. Đổi mạng triển khai chỉ cần sửa `.env`.

---

## 1. Quy ước ID (1 byte, dạng hex)

| Loại | Khoảng | Tối đa |
|---|---|---|
| Tag ID (thiết bị người dùng) | `0xD0` → `0xEF` | 32 |
| UWB Master ID | `0xF0` → `0xFF` | 16 |
| UWB Slave ID | `0x01` → `0xCF` | 208 |
| Wifi ID | `0x11` → `0x1F` | 16 |
| BLE ID | `0x21` → `0x2F` | 16 |

> **Lưu ý hex trong topic:** topic MQTT phân biệt hoa/thường và padding. Firmware có thể
> gửi `0xF0`/`0xf0`/`0x0f0`/`0x01`/`0x1`... Runtime trilateration vì vậy **subscribe nhiều
> biến thể** của mỗi id (`_topic_hex_variants`). Khi thêm runtime mới dùng id hex nên làm tương tự.

---

## 2. DEVICE → SERVER

### 2.1 UWB Ranging  — ✅ (Algorithm 2 & 5)
- **Topic:** `2/uwb_ranging/<master_id_hex>/<slave_id_hex>`
- **Payload (chuỗi, KHÔNG phải JSON):** `<tag_id_hex>,<dist_cm>,<tag_id_hex>,<dist_cm>,...`
  (các cặp lặp lại; khoảng cách là **cm, CHƯA lọc**). Range được gom theo **slave** trong topic;
  master góp vị trí anchor.
- **Ví dụ** (topic `2/uwb_ranging/0xF0/0x01`): `0xD0,120,0xC0,500`
- Server xử lý: `backend/mqtt_handle/trilateration_uwb/runtime.py` (`UWBRuntime`) → `_handle_range`
  — dùng chung cho cả thuật toán 2 và 5 (chọn bộ não theo `run["algorithm"]`). (Trang algo-2 cũ
  **legacy** `trilateration_LM/runtime.py` cũng nghe topic này nhưng không dùng cho code mới.)
  
```json
  Topic "2/uwb_ranging/0xF0/0x01": 0xC0,345,0xD0,120
  Topic "2/uwb_ranging/0xF0/0x02": 0xC0,512,0xD0,430
  Topic "2/uwb_ranging/0xF0/0x03": 0xC0,210,0xD0,680
  Topic "2/uwb_ranging/0xF0/0x04": 0xC0,640,0xD0,295
```

### 2.2 UWB gửi data (IMU / valve / button) — ✅ (Algorithm 2 & 5)
- **Topic:** `uwb_id/<tag_id_hex>`
- **Payload (JSON):**
```json
{
  "bno": {
    "acc":   { "x": 0.12, "y": -0.45, "z": 9.81 },
    "gyro":  { "x": 0.03, "y": -0.01, "z": 1.25 },
    "mag":   { "x": 32.5, "y": -14.8, "z": 5.2 },
    "euler": { "yaw": 182.4, "roll": -2.7, "pitch": 1.3 }
  },
  "valve":  { "open": 75.5, "mode": 100 },
  "button": { "A": 0, "B": 0, "C": 1 }
}
```
- `valve.open` = độ mở van (%), `valve.mode` = chế độ phun (gửi dạng %). `button.*` = bool.
- **Chỉ dùng cho FOV + mô phỏng chữa cháy, KHÔNG dùng để định vị.** Thiết bị UWB thật thường chỉ
  gửi `valve.open` (không có `valve.mode`) → chế độ phun mặc định là "spread"; chỉ thiết bị ADMIN
  ảo mới "jet".
- Server xử lý: `trilateration_uwb/runtime.py` (`UWBRuntime`) → `_parse_user_payload` →
  `UWBManager.feed_user`.

### 2.3 RSSI chế độ Reality — ✅ (Algorithm 3 runtime)
- **Topic:** `reality_id/<tag_id_hex>`
- Server xử lý: `backend/mqtt_handle/transformer_pdr_eskf/runtime.py` → `_parse_reality_payload`
  → `Algorithm3Manager.feed` (Transformer+PDR+ESKF).
- **Payload (JSON):** gồm `rssi_wifi` + `rssi_ble` (4 kênh mỗi loại) + `bno` + `valve` + `button`.
```json
{
  "rssi_wifi": { "1": -45.5, "2": -61.2, "3": -70.8, "4": -83.1 },
  "rssi_ble":  { "1": -58.3, "2": -67.9, "3": -74.6, "4": -88.0 },
  "bno": {
    "acc":   { "x": 0.12, "y": -0.34, "z": 9.81 },
    "gyro":  { "x": 0.02, "y": -0.01, "z": 1.45 },
    "mag":   { "x": 31.7, "y": -12.5, "z": 6.9 },
    "euler": { "yaw": 178.4, "roll": -1.8, "pitch": 3.2 }
  },
  "valve":  { "open": 65.5, "mode": 100 },
  "button": { "A": 1, "B": 0, "C": 1 }
}
```

### 2.4 RSSI chế độ Training (thu fingerprint) — ✅
- **Topic:** `training_id/<tag_id_hex>`  (đây là `mqtt_topic` truyền vào `/api/data-collection/start`).
- **Payload (JSON):** giống 2.3 nhưng **chỉ cần** `rssi_wifi` + `rssi_ble` + `bno`
  (không cần valve/button).
```json
{
  "rssi_wifi": { "1": -46.2, "2": -59.8, "3": -71.4, "4": -82.7 },
  "rssi_ble":  { "1": -55.1, "2": -63.9, "3": -77.2, "4": -89.5 },
  "bno": {
    "acc":   { "x": 0.08, "y": -0.21, "z": 9.79 },
    "gyro":  { "x": 0.01, "y": -0.03, "z": 1.12 },
    "mag":   { "x": 28.4, "y": -10.7, "z": 7.5 },
    "euler": { "yaw": 184.6, "roll": -1.5, "pitch": 2.8 }
  }
}
```
- Server xử lý: `backend/mqtt_handle/fingerprints_collectdata/collector.py` → `_parse_payload`
  → lưu DB (`crud.create_fingerprint`). **RSSI được làm tròn lưu kiểu INT**; acc/gyro/mag/euler float.

> Lưu ý xử lý RSSI ở thuật toán fingerprint (training & runtime): chỉ giữ giá trị trong dải
> hợp lệ **[-99, -1] dBm**; ngoài dải bị loại bỏ (xem `backend/algorithms/transformer`).

---

## 3. SERVER → DEVICE

### 3.1 Map — ✅
- **Topic:** `map_data`
- **Phát từ:** `POST /api/maps/{map_id}/send-map-mqtt` → `mqtt_client.publish(...)`.
- **Payload (JSON):**
```json
{
  "info": { "x": 10, "y": 20, "north_offset": 90 },
  "cells": [ [0, 5], [4, 5], [5, 5] ]
}
```
- `info.x`/`info.y` = kích thước map (mét, int) = `length_x`/`width_y`; `north_offset` =
  `maps.offset_angles` (float). `cells` = danh sách `[x, y]` góc dưới-trái của **các ô ĐI ĐƯỢC**.

### 3.2 Vị trí người dùng — ✅ (runtime thuật toán 2, 3, 5)
- **Topic:** `user_pos/<tag_id_hex>`
- **Payload (JSON):**
```json
{ "x": 3.6, "y": 3.6, "score": 100 }
```
- `x`,`y` = tọa độ định vị (float, đã kẹp trong map), `score` = điểm bài tập hiện tại (int).
- Phát từ `backend/mqtt_handle/server_2_device/publish_user_pos` — gửi khi runtime giải ra vị trí
  mới, và trong vòng lặp mô phỏng khi `(x, y, score)` (làm tròn) thay đổi.
- **Mỗi thiết bị publish đúng hex id của nó.** Thiết bị **ADMIN ảo** cũng publish
  `user_pos/<ADMIN_HEX>` y như một thiết bị thật (áp dụng cho cả thuật toán 2/3/5).

### 3.3 Firefighting data — ✅ (mô phỏng phiên huấn luyện, thuật toán 2/3/5)
- **Topic:** `fire_data`
- **Payload (JSON):**
```json
{
  "fires_num": 2,
  "fires": [
    { "x": 3, "y": 6, "level": 3 },
    { "x": 1, "y": 2, "level": 2 }
  ]
}
```
- `fires_num` = tổng số ngọn lửa (gốc + lan) có level>0; mỗi phần tử: `x`,`y` = ô
  (góc dưới-trái, int), `level` = mức 0–5 (int).
- Phát từ `backend/mqtt_handle/server_2_device/publish_fire_data` (vòng lặp mô phỏng).
  Quy tắc: ô vừa tắt vẫn được gửi kèm `level=0` và vẫn được đếm trong `fires_num` ở MỘT tin,
  tin kế tiếp mới bỏ ô và giảm `fires_num`. Xem `READ_ME/Algorithm/Algorithm_simu.md`.

---

## 4. Bảng tổng hợp

| Hướng | Topic | Payload | Server xử lý / phát | Trạng thái |
|---|---|---|---|---|
| D→S | `2/uwb_ranging/<master>/<slave>` | chuỗi cặp `tag,dist_cm` | trilateration_uwb/runtime.py (algo 2/5; + legacy trilateration_LM) | ✅ |
| D→S | `uwb_id/<tag>` | JSON bno/valve/button | trilateration_uwb/runtime.py (algo 2/5; + legacy trilateration_LM) | ✅ |
| D→S | `training_id/<tag>` | JSON rssi+bno | fingerprints_collectdata/collector.py | ✅ |
| D→S | `reality_id/<tag>` | JSON rssi+bno+valve+button | transformer_pdr_eskf/runtime.py (algo 3) | ✅ |
| S→D | `map_data` | JSON info+cells | /api/maps/{id}/send-map-mqtt | ✅ |
| S→D | `user_pos/<tag>` | JSON x,y,score | server_2_device/publisher.py (algo 2/3/5 + ADMIN) | ✅ |
| S→D | `fire_data` | JSON fires | server_2_device/publisher.py (algo 2/3/5) | ✅ |

> Tất cả topic trong hợp đồng (`Source/mqtt_topic.txt`) đã được hiện thực. `reality_id` phục vụ
> thuật toán 3; `2/uwb_ranging` + `uwb_id` phục vụ thuật toán 2 & 5; `user_pos`/`fire_data` là
> kết quả định vị + mô phỏng dùng chung cho cả 3 thuật toán (xem
> `READ_ME/Algorithm/Algorithm_simu.md`).
