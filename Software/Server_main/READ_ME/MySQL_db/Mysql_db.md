# Cơ Sở Dữ Liệu MySQL — Mô Tả Cho Developer

Tài liệu mô tả toàn bộ database của server. Schema chuẩn (nguồn duy nhất) nằm ở `db/init.sql`;
file này diễn giải lại cho người đọc để hiểu mà **không cần mở server**.

- **Tên database:** `indoor_positioning_db`
- **Charset/Collation:** `utf8mb4` / `utf8mb4_unicode_ci`
- **Engine:** InnoDB (mọi bảng) — hỗ trợ khóa ngoại + ràng buộc CHECK (yêu cầu MySQL **8.0.16+**)
- **Khởi tạo:** `db/init.sql` (chạy 1 lần khi dựng) hoặc `python backend/init_db.py`.

---

## 1. Sơ đồ quan hệ (tổng quan)

```
account ──< session_history >── device
                  │
maps ──< session >┘
 │  │      │
 │  │      └──< session_fire
 │  ├──< map_cells ──< fingerprint_data >── measurement_campaigns >── maps
 │  ├──< map_beacon
 │  └──< map_algorithm
schema_migrations  (bảng kỹ thuật, theo dõi migration một chiều)
```

> `A ──< B`: một bản ghi A liên kết nhiều bản ghi B (1–N). Hầu hết khóa ngoại theo `maps` đều
> `ON DELETE CASCADE` (xóa map sẽ xóa theo cell/beacon/algorithm/session...).

---

## 2. Chi tiết từng bảng

### `schema_migrations` — theo dõi migration
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `migration_id` | VARCHAR(100) PK | Mã migration đã áp dụng |
| `applied_at` | TIMESTAMP | Thời điểm áp dụng |

Dùng để các migration "một chiều" (vd đổi tên cột yaw/roll/pitch) **không chạy lại lần hai**.

### Bảng 1 — `maps` (thông tin tổng quan bản đồ)
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `map_id` | INT PK AI | |
| `map_name` | VARCHAR(100) | Có index |
| `length_x` | INT | Số ô theo trục X (Ox) |
| `width_y` | INT | Số ô theo trục Y (Oy) |
| `offset_angles` | DECIMAL(6,2) = 0 | Góc lệch bản đồ so với hướng Bắc thật (độ, theo chiều kim đồng hồ) — dùng để quy đổi yaw thô sang heading theo bản đồ |
| `created_at` | TIMESTAMP | |

### Bảng 2 — `map_cells` (ô lưới 1m×1m)
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `cell_id` | INT PK AI | |
| `map_id` | INT FK→maps | CASCADE |
| `cell_index` | INT | Số thứ tự ô (1 .. length_x×width_y) |
| `coord_x`, `coord_y` | INT | Tọa độ góc dưới-trái của ô |
| `is_passable` | TINYINT(1) = 1 | `1` = đi được, `0` = bị chặn (tường/chướng ngại) |

Ràng buộc duy nhất: `(map_id, cell_index)` và `(map_id, coord_x, coord_y)`.

### Bảng 3 — `measurement_campaigns` (chiến dịch thu fingerprint)
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `campaign_id` | INT PK AI | |
| `map_id` | INT FK→maps | CASCADE |
| `sample_number` | INT = 0 | Số mẫu mục tiêu mỗi ô (collector tự dừng khi đủ) |
| `campaign_name` | VARCHAR(100) NULL | Tên/mô tả tùy chọn |
| `measured_at` | TIMESTAMP | |

### Bảng 4 — `fingerprint_data` (mẫu cảm biến thô)
| Nhóm cột | Kiểu | Ghi chú |
|---|---|---|
| `fingerprint_id` | BIGINT PK AI | |
| `campaign_id` | INT FK→measurement_campaigns | CASCADE |
| `cell_id` | INT FK→map_cells | CASCADE |
| `wifi_rssi_1..4` | INT NULL | RSSI WiFi 4 AP (dBm) |
| `ble_rssi_1..4` | INT NULL | RSSI BLE 4 beacon (dBm) |
| `acc_x/y/z` | FLOAT NULL | Gia tốc kế (m/s²) |
| `gyro_x/y/z` | FLOAT NULL | Con quay (rad/s) |
| `mag_x/y/z` | FLOAT NULL | Từ kế (μT) |
| `yaw`, `roll`, `pitch` | FLOAT NULL | Góc Euler (độ) — thứ tự đúng theo MQTT là **yaw(heading)/roll/pitch** |
| `collected_at` | TIMESTAMP | |

> **Lưu ý migration thứ tự góc:** parser cũ từng lưu nhầm 3 trường cuối theo `roll/pitch/yaw`.
> `init.sql` có block migration (idempotent, ghi vào `schema_migrations`) chỉ **đổi tên cột** về
> đúng `yaw/roll/pitch`, **không** sửa giá trị đã lưu. RSSI hợp lệ trong `[-99, -1] dBm`; mẫu
> ngoài dải bị thuật toán bỏ qua (xem tài liệu thuật toán 3).

### Bảng 5 — `account` (người dùng)
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `username` | VARCHAR(50) PK | |
| `password` | VARCHAR(255) | **Lưu plaintext** (hệ thống nội bộ, không hash) |
| `role_id` | TINYINT | CHECK ∈ {1,2,3}: `1=admin, 2=trainer, 3=trainee` |
| `created_at` | TIMESTAMP | |

3 tài khoản mặc định tạo sẵn: `admin/admin`, `trainer/trainer`, `trainee/trainee`.

### Bảng 6 — `device` (thiết bị vật lý)
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `device_id` | INT PK AI | |
| `device_name` | VARCHAR(100) UNIQUE | |
| `device_hex_id` | VARCHAR(32) UNIQUE | Mã hex in trên thiết bị, vd `0xAB` |
| `water_capacity` | INT = 100 | Sức chứa bình nước. CHECK `>= -1`: **`-1` = vô hạn** (không bao giờ cạn), **`>=0` = hữu hạn** (cạn khi phun, nạp lại ở điểm tập kết). Cùng đơn vị với `WATER_MAX` của mô phỏng |
| `created_at` | TIMESTAMP | |

### Bảng 6.1 — `map_beacon` (beacon theo bản đồ)
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `beacon_id` | BIGINT PK AI | |
| `map_id` | INT FK→maps | CASCADE |
| `beacon_hex_id` | VARCHAR(32) | Duy nhất theo `(map_id, beacon_hex_id)` |
| `beacon_type` | TINYINT | CHECK ∈ {1,2,3,4}: `1=wifi, 2=ble, 3=uwb_slave, 4=uwb_master` |
| `coord_x`, `coord_y` | DECIMAL(10,2) | Tọa độ beacon (đơn vị ô lưới = mét) |
| `created_at` | TIMESTAMP | |

> **Quy tắc nghiệp vụ (ép ở tầng API, không phải DB):** mỗi bản đồ **tối đa 1 UWB master**.

### Bảng 6.2 — `map_algorithm` (thuật toán bật cho mỗi map)
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `map_id` | INT | PK kép `(map_id, algorithm)`, FK→maps CASCADE |
| `algorithm` | TINYINT | CHECK ∈ {1,2,3,4,5} |
| `created_at` | TIMESTAMP | |

`algorithm`: `1`=CNN+PDR, `2`=Trilateration LM (loosely), `3`=Transformer+PDR+ESKF,
`4`=Multi-modal cross attention, `5`=Trilateration EKF (tightly).

> Khi lưu thuật toán cho map, API kiểm tra beacon: fingerprint (1/3/4) cần ≥3 wifi/ble;
> trilateration UWB (2 **và** 5) cần ≥3 UWB beacon gồm ≥1 UWB master.

### Bảng 7 — `session` (kịch bản huấn luyện)
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `session_id` | INT PK AI | (tên bảng có backtick vì `session` là từ khóa) |
| `session_name` | VARCHAR(100) | |
| `map_id` | INT FK→maps | CASCADE |
| `duration_seconds` | INT | Thời lượng huấn luyện (giây) |
| `created_at` | TIMESTAMP | |

### Bảng 8 — `session_fire` (mốc thời gian đám cháy của phiên)
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `session_fire_id` | BIGINT PK AI | |
| `session_id` | INT FK→session | CASCADE |
| `fire_time_seconds` | INT | Thời điểm bùng cháy (offset từ lúc bắt đầu) |
| `fire_level` | INT | Cấp độ lửa |
| `fire_spread` | INT = 0 | Tốc độ lan (số ô mỗi bước lan) |
| `fire_spread_time` | INT = 0 | Khoảng cách giữa các bước lan (giây) |
| `cell_index` | INT | Ô bùng cháy |
| `coord_x`, `coord_y` | INT | Tọa độ ô bùng cháy |
| `created_at` | TIMESTAMP | |

> 2 cột `fire_spread`/`fire_spread_time` có sẵn trong `init.sql` (kèm block migration nội bộ cho
> DB cũ). Một sự kiện cháy lưu **cả** `cell_index` lẫn `(coord_x, coord_y)`.

### Bảng 9 — `session_history` (phiên đã hoàn thành)
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `session_history_id` | BIGINT PK AI | |
| `username` | VARCHAR(50) FK→account | ON DELETE RESTRICT |
| `device_id` | INT FK→device | ON DELETE RESTRICT |
| `session_id` | INT FK→session | CASCADE |
| `completion_seconds` | INT | Thời gian hoàn thành |
| `score` | INT = 0 | Điểm |
| `completed_at` | TIMESTAMP | |

> Chỉ ghi khi phiên kết thúc. Thiết bị ADMIN ảo **không** được lưu vào đây (không có `device_id`).
> Với thuật toán mô phỏng (2/3/5), bản ghi do mô phỏng tự lưu khi kết thúc tự nhiên; bấm Stop =
> không lưu. Thuật toán không mô phỏng (1/4) lưu qua `/api/training/finish`.

---

## 3. Khởi tạo & cập nhật DB

- **Dựng mới:** chạy `db/init.sql` (tạo DB nếu chưa có, tạo toàn bộ bảng, tạo 3 tài khoản mặc
  định). `init.sql` an toàn khi chạy lại với phần lớn bảng (`CREATE TABLE IF NOT EXISTS`), **trừ**
  `device` và `session_history` bị `DROP ... IF EXISTS` rồi tạo lại — cẩn thận khi chạy trên DB
  đang có dữ liệu thật.
- **DB đã tồn tại:** chạy file migration trong `db/`. Hiện chỉ có `db/device_water_add.sql` (thêm
  cột `water_capacity`). Mở trong MySQL Workbench → **Execute all** (dùng prepared statement nên
  phải chạy nguyên file). File an toàn khi chạy lại.

---

## 4. Lưu trữ dữ liệu khác (ngoài MySQL)

Hầu hết dữ liệu nằm trong MySQL. Một số artifact **không** ở DB:
- **Model thuật toán 3 (Transformer):** lưu trên đĩa tại
  `backend/algorithms/transformer/model/map_<id>/campaign_<id>/` (`transformer_model.pt`,
  `scaler.joblib`, log, biểu đồ, CSV metric).
- **Trạng thái huấn luyện real-time + mô phỏng:** chỉ nằm **trong RAM** (`active_training_runs`,
  các vòng lặp mô phỏng) — mất khi restart server, không ghi DB cho tới khi phiên kết thúc.
- **Ảnh thiết bị/bản đồ:** file tĩnh trong `frontend/img/` (không lưu DB).
