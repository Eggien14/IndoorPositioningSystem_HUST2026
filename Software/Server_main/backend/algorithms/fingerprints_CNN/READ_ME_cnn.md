# Fingerprints CNN — Thuật toán 1 (RSSI Fingerprints, mô tả theo server cũ)

Module này là **Thuật toán 1**: định vị bằng **fingerprint RSSI** + mạng học sâu phân loại ô.
Trong server hiện tại, thư mục `backend/algorithms/fingerprints_CNN/` **mới chỉ có tài liệu**
(placeholder) — phần code CHƯA được triển khai lại. Tài liệu này mô tả **chính xác phần CNN của
server kỳ trước** (đã chạy thật) để phục vụ báo cáo và làm cơ sở khi triển khai lại sau này.

> **Phạm vi:** chỉ mô tả khối **CNN / fingerprint** (bỏ qua PDR và Kalman filter của server cũ
> theo yêu cầu). Server cũ là dự án Django ở `Source/Server/config/` — **chỉ tham khảo, KHÔNG
> import/chạy**. Đối chiếu nguồn + chi tiết kiến trúc: [reference_cnn.txt](reference_cnn.txt).

---

## 1. Vai trò trong bài toán IPS

Model fingerprint nhận **RSSI** làm đầu vào và **phân loại ra `location`** (một ô/điểm đã khảo
sát trên bản đồ), sau đó tra toạ độ thật của ô đó để cập nhật vị trí người dùng.

```
RSSI (rssi1..4) ─► [Model fingerprint] ─► location (nhãn lớp) ─► tra (axis_x, axis_y) ─► vị trí
```

Khác hẳn nhóm trilateration (algo 2/5, tính hình học) và nhóm hồi quy toạ độ (algo 3 Transformer
cho ra (x,y) liên tục): fingerprint CNN coi định vị là **bài toán PHÂN LOẠI** — mỗi ô khảo sát là
một lớp, model đoán lớp rồi map sang toạ độ rời rạc của ô đó.

---

## 2. Vị trí trong source code cũ (Source/Server/config — tham khảo)

| Thành phần | File (server cũ) |
|---|---|
| Định nghĩa model + train + predict | `target_tracking/ml_model.py` (`feedforward`, `MLModel`) |
| Lọc RSSI (WBO) | `target_tracking/wbo_filter.py` (`WBOFilter`, `preprocessor`) |
| Model đã train | `target_tracking/model/ml_model.keras` |
| Bảng dữ liệu train | `RSSI_for_Training` trong `target_tracking/models.py` (rssi1..4, location, axis_x, axis_y) |
| Kích hoạt train | qua WebSocket `/ws/web/training/` (`{"action":"run_model"}`) |
| Predict realtime | `target_tracking/monitoring.py` (`read_data.runmodel` + `process_message`) |

Stack cũ: **TensorFlow/Keras** (khác stack hiện tại của server mới là PyTorch cho algo 3).

---

## 3. Kiến trúc model

Server cũ tồn tại **hai phiên bản**:

### 3a. CNN thật (bản gốc — hiện đang bị comment trong `ml_model.py`)
Xử lý RSSI theo **cửa sổ 10 mẫu liên tiếp**; với 4 kênh RSSI, input reshape thành **(4, 10, 1)**
(4 hàng = 4 kênh, 10 cột = 10 mẫu theo thời gian, 1 = channel cho Conv2D). Trước khi đưa vào CNN,
mỗi RSSI được lọc bằng **WBOFilter** trong cửa sổ.

```
Input (4,10,1)
  → Conv2D(16,(3,3),relu) → BatchNormalization
  → Conv2D(32,(2,2),relu) → Conv2D(32,(1,1),relu) → Conv2D(64,(1,1),relu)
  → Flatten
  → Dense(256,relu) → Dropout(0.3) → Dense(128,relu) → Dense(128,relu)
  → Dense(num_classes, softmax)
```

### 3b. Dense feedforward (bản ĐANG CHẠY ở server cũ)
Phần không-comment hiện tại **không còn là CNN đúng nghĩa** (class vẫn tên `feedforward` nhưng là
mạng Dense), input là **vector 4 chiều** `[rssi1, rssi2, rssi3, rssi4]` (một mẫu, không cửa sổ):

```
Input [4]
  → Dense(512,relu) → Dropout(0.3)
  → Dense(512,relu) → Dropout(0.3)
  → Dense(256,relu) → Dropout(0.2)
  → Dense(128,relu) → Dropout(0.1)
  → Dense(128,relu)
  → Dense(num_classes, softmax)
```

`num_classes = số ô khảo sát của map` (`map.total_units`). Nhãn lấy bằng
`label = prediction.argmax(axis=1)[0] + 1` (cộng 1 vì `location` trong DB đánh số từ 1).

> Tóm lại: tên thư mục là "CNN" theo mục tiêu ban đầu (fingerprint CNN), nhưng bản chạy thật của
> server cũ là Dense feedforward; CNN đúng nghĩa vẫn còn trong comment để tham khảo.

---

## 4. Tiền xử lý & huấn luyện (bản Dense đang chạy)

`MLModel.standardize_data()`:
1. Shuffle dữ liệu (`sample(frac=1)`).
2. Tách input `X = [rssi1..4]`, output `y = [location]`.
3. **Chuẩn hoá min-max từng cột RSSI:** `X = (X - min) / (max - min)` (lưu lại `min/max` để dùng
   khi predict realtime).
4. One-hot encode nhãn `location`.
5. Train: `epochs=200`, `batch_size=32`, `validation_split=0.2`, loss `categorical_crossentropy`,
   optimizer `Adam` + `ExponentialDecay(lr0=1e-3, decay_steps=8000, decay_rate=0.96)`.

Luồng train kích hoạt từ trang training (WebSocket): lấy map hiện tại → `num_classes =
map.total_units` → query `RSSI_for_Training` (`rssi1..4, location`) → tạo `MLModel` →
`train_model()` → `save_model()` (`model/ml_model.keras`) → gửi validation accuracy về frontend.

### WBO filter (`wbo_filter.py`)
Bộ lọc RSSI dùng ở bản CNN (cửa sổ 10 mẫu) để làm sạch tín hiệu trước khi đưa vào mạng. Bản Dense
đang chạy **bỏ qua** bước này (`smoothing_data()` không được gọi trong `standardize_data`).

---

## 5. Predict realtime (server cũ)

`monitoring.py`:
1. `runmodel()`: load `model/ml_model.keras`, tính `min/max` RSSI từ dữ liệu train của map (để
   chuẩn hoá realtime giống lúc train).
2. `process_message()`: lấy 4 RSSI mới nhất từ MQTT → chuẩn hoá `(data - min)/(max - min)` →
   `model.predict` → `label = argmax + 1` → tra `(axis_x, axis_y)` của `location=label` trong
   `RSSI_for_Training` → cập nhật vị trí người dùng.

> Lưu ý trạng thái code cũ: trong `Monitoringconsumer.connect()`, dòng `self.data.runmodel()` đang
> bị comment — nếu không có chỗ khác gọi `runmodel()` thì realtime chưa load model/chưa có min-max.

---

## 6. Giới hạn & việc còn lại

- **Định vị rời rạc:** đầu ra là **ô** (lớp), độ phân giải bằng kích thước ô khảo sát — không cho
  toạ độ liên tục như algo 3. Sai số phụ thuộc mật độ khảo sát fingerprint.
- **Một mẫu, không thời gian (bản Dense):** dễ nhiễu hơn bản CNN cửa sổ 10 mẫu + WBO filter.
- **Chưa triển khai ở server mới:** thư mục `fingerprints_CNN/` của server hiện tại trống; nếu
  triển khai lại nên dùng schema fingerprint mới (`fingerprint_data` có wifi×4/ble×4 — xem
  `READ_ME/MySQL_db/Mysql_db.md`) và dải RSSI hợp lệ `[-99,-1]` (đồng bộ với algo 3).
- **Stack:** server cũ dùng Keras; server mới dùng PyTorch — khi làm lại nên thống nhất theo
  server mới.

> Tài liệu tổng (coordinator) cho thuật toán 1: `READ_ME/Algorithm/Algorithm_1.md`.
