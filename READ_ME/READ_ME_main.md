# Hệ Thống Định Vị Trong Nhà & Huấn Luyện Chữa Cháy — Tài Liệu Tổng (cho Developer)

> Đây là **file đọc đầu tiên** cho mọi developer/thành viên đồ án. Nó mô tả tổng quan toàn bộ
> server và đóng vai trò **điều phối (coordinator)**: từ đây liên kết tới các tài liệu chi tiết
> hơn trong thư mục `READ_ME/`. Không cần đi sâu từng dòng — phần chi tiết để các file con đảm nhiệm.
>
> (Tài liệu này dành cho người. Bộ tài liệu song song dành cho AI agent là các file `CLAUDE*.md`
> nằm rải trong mã nguồn; hai bộ viết độc lập, hạn chế trích dẫn lẫn nhau.)

---

## 1. Hệ thống này là gì?

Một **ứng dụng web chạy nội bộ (local)** phục vụ huấn luyện chữa cháy trong nhà, gồm các năng lực:

1. **Quản lý bản đồ**: tạo/sửa bản đồ dạng lưới ô 1m×1m, đặt beacon (WiFi/BLE/UWB), cấu hình
   thuật toán định vị cho từng bản đồ.
2. **Thu thập dữ liệu fingerprint**: thu mẫu RSSI + IMU theo từng ô lưới (qua MQTT) để huấn luyện
   các thuật toán fingerprint.
3. **Định vị real-time**: nhận dữ liệu cảm biến từ thiết bị (tag) qua MQTT, ước lượng vị trí
   người trong nhà bằng nhiều thuật toán khác nhau, hiển thị trực tiếp trên trang web.
4. **Mô phỏng kịch bản chữa cháy**: lan lửa theo lưới ô, người tham gia "phun nước" dập lửa, hệ
   thống chấm điểm và lưu lịch sử.

Người dùng có 3 vai trò: `1=admin`, `2=trainer`, `3=trainee` (phân quyền **phía client**, không
có token/middleware — xem mục 6).

---

## 2. Công nghệ sử dụng

| Lớp | Công nghệ |
|---|---|
| Backend | FastAPI 0.109.1, Python 3.12 |
| Giao diện | Jinja2 (render HTML phía server) + vanilla JS (không framework) |
| Cơ sở dữ liệu | MySQL (mysql-connector-python 8.3.0) |
| Truyền thông | MQTT (paho-mqtt 2.0.0) |
| ML/Toán | numpy, scipy, scikit-learn, torch (CPU) |
| Server | uvicorn 0.27.0 |

Chi tiết cài đặt môi trường & chạy: **`READ_ME/Started/Env.md`** (dựng venv, thư viện, `.env`,
khởi tạo DB) và **`READ_ME/Started/Scripts.md`** (script bật/tắt server). Tóm tắt nhanh nhất:

```powershell
.\scripts\start_server.ps1          # chạy tại http://127.0.0.1:8000
```

---

## 3. Kiến trúc tổng thể

```
Thiết bị (tag/firmware)
        │  MQTT (RSSI, IMU, UWB ranging, valve...)
        ▼
┌─────────────────────────────────────────────────────────┐
│  backend/ (FastAPI)                                       │
│   • mqtt_client.py        — lớp truyền tải MQTT (singleton)│
│   • mqtt_handle/          — handler theo nhiệm vụ          │
│       thu data / định vị algo 3 / định vị UWB 2&5 /        │
│       publish kết quả về thiết bị                          │
│   • algorithm_2/3/5.py    — "bộ não" định vị mỗi tag       │
│   • algorithm_uwb.py, algorithm_3.py — coordinator chạy thật│
│                            + mô phỏng + thiết bị ADMIN ảo  │
│   • simulation/           — lan lửa / dập lửa / tính điểm  │
│   • crud.py + database.py — đọc/ghi MySQL                  │
│   • main.py               — toàn bộ route (API + trang)    │
└─────────────────────────────────────────────────────────┘
        │  render HTML + JSON API                  │  MQTT (user_pos, fire_data)
        ▼                                          ▼
   frontend/ (trình duyệt)                    Thiết bị (hiển thị vị trí, lửa)
        │
        ▼
     MySQL (bản đồ, fingerprint, thiết bị, phiên, lịch sử)
```

Bản đồ thư mục đầy đủ + nhiệm vụ từng file: **`READ_ME/Structure/File_structure.md`**.

---

## 4. Các thuật toán định vị

Có **5 thuật toán** (`ALGORITHM_NAMES` trong `backend/main.py`). Ba thuật toán đã chạy real-time
đầy đủ kèm mô phỏng chữa cháy; thuật toán 1 & 4 hiện là stub.

| ID | Tên | Real-time | Tài liệu tổng (dev) |
|----|------|-----------|---------------------|
| 1 | RSSI Fingerprints - CNN + PDR | Stub (mô tả theo server cũ) | `READ_ME/Algorithm/Algorithm_1.md` |
| 2 | Trilateration: Robust LM (loosely-coupled) | ✅ | `READ_ME/Algorithm/Algorithm_2.md` |
| 3 | RSSI Fingerprints - Transformer + PDR + ESKF | ✅ | `READ_ME/Algorithm/Algorithm_3.md` |
| 4 | RSSI Fingerprints - Multi modal cross attention | Stub | — |
| 5 | Trilateration: Tightly-coupled EKF | ✅ | `READ_ME/Algorithm/Algorithm_5.md` |

- **Thuật toán 3** là sự kết hợp 3 khối: Transformer (RSSI→tọa độ) + PDR (IMU→độ dời) + ESKF
  (hợp nhất). Mỗi khối có tài liệu riêng: `backend/algorithms/{transformer,pdr,eskf}/READ_ME_*.md`
  (mô tả) và `reference_*.txt` (tham khảo + kết quả).
- **Thuật toán 2 & 5** dùng UWB ranging, **chung một pipeline real-time**, chỉ khác bộ não định vị
  (LM vs EKF). Tài liệu: `backend/algorithms/trilateration_LM/READ_ME_tri_lm.md` và
  `trilateration_ekf/READ_ME_tri_ekf.md` (+ `reference_*.txt`).
- **Mô phỏng chữa cháy** (lan lửa / dập lửa / chấm điểm) dùng chung cho cả algo 2/3/5:
  **`READ_ME/Algorithm/Algorithm_simu.md`**.

> Mỗi trang con `Algorithm_2/3/5.md` đóng vai trò coordinator phụ cho thuật toán đó: đọc trước,
> rồi đi tới các `READ_ME_*.md`/`reference_*.txt` từng khối để hiểu sâu hơn.

---

## 5. Cơ sở dữ liệu & truyền thông

- **Database (MySQL):** schema chuẩn ở `db/init.sql` (chạy 1 lần khi dựng). Mô tả bảng/quan hệ/quy
  tắc cho dev: **`READ_ME/MySQL_db/Mysql_db.md`**. DB cũ cập nhật bằng migration trong `db/`
  (hiện có `device_water_add.sql`).
- **MQTT/Truyền thông:** quy ước topic + cấu trúc tin nhắn (định vị, thu data, mô phỏng) cho dev:
  **`READ_ME/Comunicate/MQTT.md`**.

---

## 6. Những điểm quan trọng cần nhớ

1. **Phân quyền phía client.** Không có JWT/middleware; `role_id` gửi qua **query param**
   (`?role_id=`). Tin tưởng dựa trên localStorage của trình duyệt. Các thao tác ghi của
   device/session/fire chỉ cho `[1,2]` (admin/trainer); trainee chỉ chọn được 1 thiết bị.
2. **Trạng thái huấn luyện nằm trong RAM.** `active_training_runs` và các vòng lặp mô phỏng là
   in-memory → **mất khi restart server**. Frontend lưu `training_run_id` ở sessionStorage để
   khôi phục.
3. **MQTT broker đọc từ `.env`** (`MQTT_BROKER`, mặc định `localhost`). Đổi mạng chỉ cần sửa `.env`,
   không sửa code.
4. **Console chỉ in ASCII** (máy Windows cp1252 sẽ crash với ký tự đặc biệt). Giữ nguyên quy tắc này.
5. **`Source/` chỉ để tham khảo** — không bao giờ import vào server đang chạy; code thật ở `backend/`.
6. **Thiết bị ADMIN ảo**: một "thiết bị" điều khiển trên màn hình server (WASD/chuột), được chấm
   điểm như thiết bị thật trong mô phỏng và cũng publish `user_pos` theo hex của nó, nhưng không lưu
   vào lịch sử.

---

## 7. Bản đồ tài liệu (coordinator)

Toàn bộ tài liệu **cho developer** nằm trong `READ_ME/` (file này là gốc):

| Chủ đề | File |
|---|---|
| **Tổng quan server** | `READ_ME/READ_ME_main.md` ← bạn đang đọc |
| Cấu trúc thư mục (mọi file) | `READ_ME/Structure/File_structure.md` |
| Tham chiếu API HTTP | `READ_ME/Structure/API.md` |
| Sơ đồ trang & luồng | `READ_ME/Structure/Sitemap.md` |
| Dựng môi trường & chạy | `READ_ME/Started/Env.md`, `READ_ME/Started/Scripts.md` |
| Cơ sở dữ liệu | `READ_ME/MySQL_db/Mysql_db.md` |
| Truyền thông MQTT | `READ_ME/Comunicate/MQTT.md` |
| Thuật toán 1 / 2 / 3 / 5 | `READ_ME/Algorithm/Algorithm_1.md`, `Algorithm_2.md`, `Algorithm_3.md`, `Algorithm_5.md` |
| Mô phỏng chữa cháy | `READ_ME/Algorithm/Algorithm_simu.md` |
| Chi tiết từng khối thuật toán | `backend/algorithms/<block>/READ_ME_*.md` + `reference_*.txt` |

> **Lưu ý cho người không có server trong tay:** các file `READ_ME/...` được viết để hiểu được hệ
> thống mà không cần chạy thử. Khi báo cáo đồ án, đây là nguồn mô tả chính xác và đầy đủ nhất.
