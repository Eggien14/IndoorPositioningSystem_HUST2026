# Thuật Toán 1 — RSSI Fingerprints (CNN + PDR) — mô tả theo server cũ

Tài liệu tổng cho **developer** về thuật toán định vị số 1: định vị bằng **vân tay tín hiệu
RSSI** (fingerprint) + mạng học sâu phân loại ô. Đây là thuật toán của **server kỳ trước**; ở
server hiện tại thuật toán 1 **chưa được triển khai lại** (ô `/training-live` dùng chung là stub).

> **Phạm vi (theo yêu cầu):** chỉ mô tả khối **CNN / fingerprint**; **bỏ qua PDR và Kalman
> filter** của server cũ. Server cũ là dự án Django ở `Source/Server/config/` — **chỉ tham khảo,
> KHÔNG import/chạy**.
>
> Tài liệu code & lý thuyết chi tiết:
> - Mô tả module (dev): `backend/algorithms/fingerprints_CNN/READ_ME_cnn.md`
> - Đối chiếu nguồn + kiến trúc: `backend/algorithms/fingerprints_CNN/reference_cnn.txt`
> - Tên hiển thị trong server mới (`ALGORITHM_NAMES[1]`): "RSSI Fingerprints - CNN + PDR".

---

## 1. Ý tưởng tổng thể

Định vị fingerprint coi bài toán là **PHÂN LOẠI**: mỗi ô khảo sát trên bản đồ là một lớp; model
nhận RSSI và đoán lớp (ô), rồi tra toạ độ thật của ô đó.

```
RSSI (rssi1..4) ─► [Model fingerprint] ─► location (nhãn ô) ─► tra (axis_x, axis_y) ─► vị trí
```

Khác biệt với các thuật toán khác của hệ thống:
- **Algo 2/5 (trilateration):** tính hình học từ khoảng cách UWB → toạ độ liên tục.
- **Algo 3 (Transformer+PDR+ESKF):** hồi quy toạ độ liên tục (x,y) + dung hợp IMU.
- **Algo 1 (fingerprint):** **phân loại ô** → toạ độ **rời rạc** theo ô khảo sát.

---

## 2. Kiến trúc model (server cũ)

Server cũ có **hai phiên bản** (chi tiết ở `READ_ME_cnn.md` §3):

1. **CNN thật** (bản gốc, hiện đang bị comment): input cửa sổ **(4, 10, 1)** (4 kênh RSSI × 10
   mẫu liên tiếp), có **WBO filter** làm sạch RSSI; chuỗi `Conv2D → BatchNorm → Conv2D×3 →
   Flatten → Dense → softmax`.
2. **Dense feedforward** (bản đang chạy): input vector 4 chiều `[rssi1..4]` (một mẫu, không cửa
   sổ, không WBO); `Dense(512)→…→Dense(num_classes, softmax)`. Nhãn = `argmax + 1`.

`num_classes = map.total_units` (số ô khảo sát). Tên thư mục là "CNN" theo mục tiêu ban đầu, nhưng
bản chạy thật là Dense; CNN đúng nghĩa vẫn trong comment để tham khảo.

---

## 3. Huấn luyện & dự đoán (server cũ)

- **Train** (kích hoạt từ trang training qua WebSocket): query `RSSI_for_Training`
  (`rssi1..4, location`) theo map → chuẩn hoá min-max từng cột RSSI → one-hot label →
  `epochs=200, batch_size=32, val_split=0.2`, Adam + ExponentialDecay → lưu `model/ml_model.keras`.
- **Predict realtime** (`monitoring.py`): load model + `min/max` của map → lấy 4 RSSI từ MQTT →
  chuẩn hoá → predict → `label=argmax+1` → tra `(axis_x, axis_y)` của `location=label` → cập nhật.

Chi tiết từng bước (preprocess, WBO filter, lưu ý code bị comment) ở `READ_ME_cnn.md` §4–§5.

---

## 4. Kết quả

- Đánh giá là **độ chính xác phân loại ô** (top-1 location), không phải sai số mét. Server cũ trả
  `accuracy`/`val_accuracy` cuối train về frontend; không có một con số chuẩn cố định (phụ thuộc
  dữ liệu khảo sát từng map). Theo yêu cầu, **không** đưa kết quả/schema của testdata mới vào đây.

---

## 5. Trạng thái ở server mới & hướng triển khai lại

- **Chưa triển khai:** `backend/algorithms/fingerprints_CNN/` ở server mới chỉ có tài liệu
  (`READ_ME_cnn.md`, `reference_cnn.txt`); chưa có code/model. Ở UI, thuật toán 1 dùng trang
  real-time chung `/training-live` (stub), chưa có pipeline định vị/mô phỏng riêng.
- **Khi làm lại nên:** dùng schema fingerprint mới (`fingerprint_data`: wifi×4 + ble×4 + IMU) thay
  vì 4 RSSI; áp dải RSSI hợp lệ `[-99,-1]` (đồng bộ algo 3); cân nhắc quay lại CNN cửa sổ thời
  gian + temporal split (chống rò rỉ) thay vì Dense một mẫu; thống nhất stack **PyTorch** như algo
  3 (server cũ dùng Keras).

> Ghi chú: file `CLAUDE_*.md` cho AI agent của thuật toán 1 **chưa viết** (sẽ làm khi triển khai
> lại). Hiện chỉ có 2 file dev ở `backend/algorithms/fingerprints_CNN/` + file tổng này.
