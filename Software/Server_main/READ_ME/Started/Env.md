# Môi Trường & Cài Đặt Server

Tài liệu này hướng dẫn **từ đầu** cách dựng môi trường để chạy server trên một máy mới.
Viết cho cả người chưa quen lập trình — cứ làm tuần tự từng bước.

> Mọi lệnh chạy trong **PowerShell**, tại **thư mục gốc dự án** (thư mục chứa file
> `requirements.txt` và thư mục `backend/`).

---

## 1. Yêu cầu đầu vào

| Thành phần | Yêu cầu |
|---|---|
| Hệ điều hành | Windows (đang phát triển trên Windows 11) |
| Python | **3.12** (máy phát triển dùng 3.12.5). Cài từ python.org, nhớ tick "Add Python to PATH" |
| MySQL | MySQL Server 8.x đang chạy (để chứa database `indoor_positioning_db`) |
| MQTT broker | Một broker MQTT (vd Mosquitto) — chỉ cần khi chạy thu dữ liệu / định vị real-time |

Kiểm tra Python đã cài đúng chưa:
```powershell
python --version      # nên hiện Python 3.12.x
```

---

## 2. Tạo và kích hoạt môi trường ảo (venv)

Môi trường ảo giúp cô lập thư viện của dự án, không ảnh hưởng Python hệ thống.

```powershell
# Tạo venv (chỉ làm 1 lần) — sẽ tạo thư mục venv/ ở gốc dự án
python -m venv venv

# Kích hoạt venv (làm mỗi khi mở terminal mới)
.\venv\Scripts\Activate.ps1
```

Khi kích hoạt thành công, đầu dòng lệnh sẽ có tiền tố `(venv)`.

> Nếu PowerShell báo lỗi không cho chạy script, mở PowerShell quyền Admin và chạy:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` rồi thử lại.

Thoát venv khi cần: gõ `deactivate`.

---

## 3. Cài thư viện phụ thuộc

Sau khi đã kích hoạt venv:

```powershell
python -m pip install -r requirements.txt
```

Các thư viện chính trong `requirements.txt`:

| Thư viện | Phiên bản | Dùng để |
|---|---|---|
| fastapi | 0.109.1 | Web framework backend |
| uvicorn[standard] | 0.27.0 | Chạy server ASGI |
| mysql-connector-python | 8.3.0 | Kết nối MySQL |
| pydantic | 2.5.3 | Validate dữ liệu request/response |
| python-dotenv | 1.0.0 | Đọc file `.env` |
| paho-mqtt | 2.0.0 | Giao tiếp MQTT |
| torch | 2.x (CPU) | Chạy model Transformer (thuật toán 3) |
| scikit-learn | 1.8.x | Scaler cho RSSI |
| numpy, scipy, pandas, joblib, matplotlib | — | Tính toán / huấn luyện / vẽ biểu đồ |

---

## 4. Cấu hình file `.env`

Tạo (hoặc sửa) file `.env` ở **gốc dự án** với nội dung:

```
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=<mật khẩu MySQL của bạn>
DB_NAME=indoor_positioning_db

MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_KEEPALIVE=60

SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

**Lưu ý quan trọng:**
- **MQTT broker đọc từ `.env`**: `MQTT_BROKER` (mặc định `localhost`), `MQTT_PORT`,
  `MQTT_KEEPALIVE` đều lấy trong `backend/mqtt_client.py`. Khi triển khai mạng khác, chỉ cần
  sửa `MQTT_BROKER` trong `.env` (ví dụ `MQTT_BROKER=192.168.0.102`), không cần sửa code.
- `SERVER_HOST`/`SERVER_PORT` có trong `.env` nhưng script khởi động đang hard-code
  `127.0.0.1` và cổng `8000` (xem `READ_ME/Started/Scripts.md`).

---

## 5. Khởi tạo database

Đảm bảo MySQL đang chạy, sau đó nạp schema:

```powershell
# Cách 1: chạy file SQL trực tiếp bằng MySQL client
mysql -u root -p < db\init.sql

# Cách 2: dùng script Python có sẵn (đọc cấu hình từ .env)
.\venv\Scripts\python.exe backend\init_db.py
```

`db/init.sql` tạo toàn bộ bảng + 3 tài khoản mặc định (`admin/admin`, `trainer/trainer`,
`trainee/trainee`). Đây là nguồn schema chuẩn duy nhất và **chỉ chạy khi dựng DB lần đầu**;
bản thân `init.sql` đã bao gồm sẵn cột `water_capacity` của `device`, ràng buộc
`algorithm IN (1,2,3,4,5)` và 2 cột `fire_spread`/`fire_spread_time`.

Nếu **database đã có sẵn từ trước** (không dựng lại từ đầu), chạy thêm file migration trong
`db/` để cập nhật dần. Hiện chỉ có một file migration: `db/device_water_add.sql` — thêm cột
`water_capacity` (sức chứa nước mỗi thiết bị: `-1` = vô hạn, `>=0` = bình hữu hạn, mặc định
`100`). Mở file đó trong MySQL Workbench và bấm **Execute all** (vì dùng prepared statement
nên phải chạy nguyên cả file, không chạy từng dòng). File an toàn khi chạy lại nhiều lần (chỉ
thêm cột/ràng buộc nếu chưa có). Xem chi tiết DB ở `READ_ME/MySQL_db/Mysql_db.md`.

---

## 6. Chạy server

```powershell
.\scripts\start_server.ps1
```

Mở trình duyệt: `http://127.0.0.1:8000`. Chi tiết các tùy chọn khởi động/dừng server
xem `READ_ME/Started/Scripts.md`.

---

## 7. Tóm tắt quy trình lần đầu (máy mới)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# tạo file .env theo mục 4, đảm bảo MySQL chạy
mysql -u root -p < db\init.sql
.\scripts\start_server.ps1
```
