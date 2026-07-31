# Thuật Toán 3 — Transformer + PDR + ESKF

Tài liệu chi tiết cho **developer** về thuật toán định vị trong nhà số 3. Đây là hệ
**dung hợp (fusion) 3 khối**: một mô hình quan sát (Transformer học fingerprint RSSI),
một mô hình chuyển động (PDR từ IMU), và một bộ lọc dung hợp (ESKF).

> Tài liệu code chi tiết & lý thuyết của từng khối nằm trong README/reference riêng:
> - Transformer: `backend/algorithms/transformer/READ_ME_transformer.md` + `reference_transformer.txt`
> - PDR: `backend/algorithms/pdr/READ_ME_pdr.md` + `reference_pdr.txt`
> - ESKF: `backend/algorithms/eskf/READ_ME_eskf.md` + `reference_eskf.txt`
> - Mô phỏng chữa cháy (lan/dập lửa + tính điểm): `READ_ME/Algorithm/Algorithm_simu.md`
> - Đặc tả gốc (chỉ tham khảo): `Source/model_3_algorithm.txt`

---

## 1. Kiến trúc tổng thể

```
RSSI (8 kênh: wifi×4 + ble×4) ─> [Khối 1: Transformer] ─> Z_obs = (x, y) tuyệt đối ─┐
                                                                                     ├─> [Khối 3: ESKF] ─> vị trí cuối (x, y)
IMU (acc_z, yaw, ...)         ─> [Khối 2: PDR]         ─> (Δx, Δy) mỗi bước + σ ──────┘   (predict)
```

Triết lý dung hợp (nhất quán với mọi tài liệu tham khảo):
- **Transformer** cho tọa độ tuyệt đối, **không trôi** theo thời gian, nhưng **nhiễu**
  và hay **nhảy** ở vùng khuất sóng (NLOS).
- **PDR** cho quỹ đạo **mượt trong ngắn hạn**, nhưng **trôi (drift)** tích lũy dần.
- **ESKF** lấy ưu điểm của cả hai: dùng PDR để *dự đoán* (predict) giữa hai lần quan
  sát, dùng Transformer để *hiệu chỉnh* (update) chống trôi.

Điều phối toàn bộ trong `backend/algorithm_3.py` (lớp `Algorithm3`).

**Trạng thái hiện tại:** cả 3 khối đã hoàn thiện & kiểm chứng offline; **runtime MQTT real-time
đã xong** (`backend/mqtt_handle/transformer_pdr_eskf/`) kèm **trang realtime
`/training-live-algorithm3`** và **mô phỏng chữa cháy** (xem mục 8).

---

## 2. Khối 1 — Transformer (RSSI → tọa độ tuyệt đối)

**Vị trí:** `backend/algorithms/transformer/`

### Mô hình
`[B, 35, 8]` (cửa sổ 35 mẫu × 8 kênh RSSI) → `Linear(8→64)` → Positional Encoding →
`TransformerEncoder` (2 layer, 4 head, dim_ff=256, dropout 0.1) → mean-pool theo thời
gian → `Linear(64→32) → ReLU → Linear(32→2)` → `(x, y)` mét. (~102k tham số.)

### Pipeline huấn luyện (chạy ĐỘC LẬP với server, lấy dữ liệu từ MySQL)
- `training/preprocess.py`: **lọc RSSI chỉ giữ [-99, -1] dBm** (dòng có kênh null/≤-100/
  dương đều bị **loại bỏ cả dòng**); **chia train/val/test theo thời gian** trong từng
  cell (chống rò rỉ); **fit MinMaxScaler chỉ trên train**; tạo sliding window. Hàm chính
  `get_split_windows()`.
- `training/train.py`: **AdamW** (lr=1e-3, weight_decay=1e-4) + **early stopping**
  (patience=12); `EPOCHS` chỉ là trần. Tự ghi log + `training_history.csv`, tự chạy
  `evaluate.py` + `visualize.py` ở cuối.
- `training/evaluate.py`: sai số Euclid (m). `training/visualize.py`: vẽ biểu đồ loss.

### Tham số chính (`transformer/config.py`)
`MAP_ID`, `CAMPAIGN_ID`, `RSSI_VALID_MIN=-99`, `RSSI_VALID_MAX=-1`, `WINDOW_SIZE=35`,
`STEP_SIZE=5`, `SPLIT_STRATEGY="temporal"`, `D_MODEL=64`, `N_HEADS=4`, `NUM_LAYERS=2`,
`DROPOUT=0.1`, `LEARNING_RATE=1e-3`, `WEIGHT_DECAY=1e-4`, `EARLY_STOP_PATIENCE=12`.

### Kết quả
- `model/map_17/campaign_18/` (pipeline mới, temporal split): **mean 1.206 m**,
  median 1.02 m, CE90 2.15 m → đây là **độ chính xác THẬT**.
- `model/map_15/campaign_14/` (pipeline cũ, random split): 0.42 m nhưng **LẠC QUAN**
  do rò rỉ dữ liệu. **Dùng 1.2 m làm R cho ESKF, KHÔNG dùng 0.42 m.**

### Artifact runtime cần
`scaler.joblib` (load, tuyệt đối không fit lại) + `transformer_model.pt`.

---

## 3. Khối 2 — PDR (IMU → vector dịch chuyển mỗi bước)

**Vị trí:** `backend/algorithms/pdr/`  (lớp `PDRModel`, `StepEvent`, `_LowPassFilter`)

### Thuật toán
1. **Low-pass filter** (IIR bậc 1) khử nhiễu gia tốc trước khi phát hiện đỉnh.
2. **Phát hiện bước** (FSM dual-threshold trên `acc_z` tuyến tính): đỉnh cao `>1.0` rồi
   đỉnh thấp `<-1.0` trong `[100, 600] ms`.
3. **Chiều dài bước thích nghi** (thay vì cố định): Weinberg `L = K·(a_max-a_min)^0.25`
   (mặc định), hoặc Kim, hoặc fixed (fallback). FSM tích lũy a_max/a_min/mean|a| trong bước.
4. **Hướng**: `adjusted_yaw = yaw − offset_angle − offset_angle_bno`;
   `Δx = L·sin(adjusted_yaw)` (trục Ox), `Δy = L·cos(adjusted_yaw)` (trục Oy); adj=0 ⇒ +Oy.
5. Trả về `StepEvent`: `delta_x, delta_y, step_length, heading_deg, sigma_step,
   sigma_heading_deg, step_index, timestamp`. **PDR KHÔNG tự cộng dồn vị trí** — để ESKF làm.

### Tham số & hiệu chỉnh (`pdr/config.py`) cho map 17 / dữ liệu D8
- Phát hiện bước: `UPPER/LOWER_THRESHOLD=±1.0`, `MIN/MAX_STEP_TIME=100/600 ms`,
  `LOWPASS_CUTOFF_HZ=10.0` (lọc nhẹ — dữ liệu BNO khá sạch, cutoff thấp 3-5Hz sẽ mất bước).
- Chiều dài bước: `STEP_LENGTH_MODEL="weinberg"`, `WEINBERG_K=0.33`.
- Hướng: `offset_angle = −90` (thuộc **BẢN ĐỒ**: Oy=West nên offset = bearing của +Oy),
  `offset_angle_bno = −105` (thuộc **NGƯỜI/THIẾT BỊ**: đo từ 15 bước đầu đi thẳng +Oy có
  yaw_raw ~164.7°; gồm cả lệch gắn ~−90° + lệch từ trường ~−15°, KHÔNG là bội số 90°).
- Độ bất định cho ESKF: `PROCESS_NOISE_STEP_RATIO=0.15`, `PROCESS_NOISE_HEADING_DEG=3.0`.

> Quy ước map 17/D8: **Ox (5 ô) = North, Oy (10 ô) = West**. Đánh số ô: ô 1 ở góc
> dưới-trái, tăng theo Ox trước (hàng dưới: 1..5; hàng kế: 6..10).

### Kết quả hiệu chỉnh
`WEINBERG_K=0.33` cho tổng quãng đường PDR = 24.32 m so với quỹ đạo thật 24.41 m
(**sai số 0.4%**). Hướng đã khớp; phần còn lại là **drift tích lũy** → ESKF xử lý.

---

## 4. Khối 3 — ESKF (dung hợp)

**Vị trí:** `backend/algorithms/eskf/`  (lớp `ESKF2D`, `ESKFState`)

### Mô hình (error-state KF, vị trí 2D `[x, y]`)
Vì quan sát trực tiếp vị trí (H = I) nên ESKF rút gọn thành Kalman Filter tuyến tính,
nhưng vẫn giữ đúng khung error-state (predict → update → inject → reset) theo đặc tả.

**Predict** (mỗi bước PDR, control `u=[Δx,Δy]`):
```
p   ← p + u
Q   = diag(q², q²),  q = √(sigma_step² + (L·rad(sigma_heading))²),  q ≥ MIN_PROCESS_STD_M
P   ← P + Q                          (F = I)
```

**Update** (mỗi observation Transformer `z=[z_x,z_y]`):
```
δz = z − p ;  S = P + R ;  R = diag(r², r²)
Gating Mahalanobis: nếu δzᵀ S⁻¹ δz > GATING_THRESHOLD ⇒ BỎ QUA (nhảy NLOS), return False
K  = P S⁻¹ ;  δx̂ = K δz
p  ← p + δx̂   (INJECT) ;  P ← (I − K) P ;  reset δx̂ = 0
```

### Tham số (`eskf/config.py`)
- `R_MEAS_M = 1.2` — độ lệch chuẩn đo của Transformer (**lấy từ sai số thật map_17**,
  KHÔNG dùng 0.42).
- `INITIAL_POSITION_STD_M = 3.0` (P0), `MIN_PROCESS_STD_M = 0.05`.
- `GATING_THRESHOLD = 9.21` (Mahalanobis chi² 2 bậc tự do ~99%; đặt None để tắt gating).

### Giới hạn & mở rộng
- **Position-only**: ESKF kéo vị trí về observation nhưng **không sửa trực tiếp drift
  HƯỚNG** của PDR. Mở rộng: thêm trạng thái sai số hướng `δθ` (khi đó cần Jacobian → ESKF
  đầy đủ). Nâng cấp khác: Q/R thích nghi (tăng Q khi rẽ, R lớn ở vùng NLOS).

---

## 5. Điều phối — `backend/algorithm_3.py`

Lớp `Algorithm3` gắn 3 khối lại:
- `TransformerPredictor`: load `scaler.joblib` + `transformer_model.pt` từ `model_dir`,
  chạy inference cho cửa sổ RSSI (có `np.clip(scaled, 0, 1)`).
- `PDRModel` + `ESKF2D` khởi tạo tại vị trí đầu (`start_x, start_y`).

API chính:
- `process_imu(acc_z, yaw, timestamp, acc_x, acc_y)` → chạy PDR; nếu có bước thì gọi
  `ESKF.predict(...)`; trả `StepEvent`.
- `process_rssi([8 kênh RSSI], timestamp)` → **lọc dòng ngoài [-99,-1]** (bỏ qua), đẩy
  vào cửa sổ 35 mẫu; khi đủ cửa sổ + đúng nhịp `STEP_SIZE` → Transformer inference →
  `ESKF.update(...)`. Trả `(z_x, z_y, accepted)`.
- `get_state()` → `Algorithm3State(fused_x, fused_y, pos_std, step_count, update_count,
  rejected_count, last_obs, last_step)`.

### Kết quả kiểm chứng end-to-end (D8_1_1, map_17)
- ESKF fused: điểm cuối **(1.96, 0.52)** so với thật **(1.5, 0.5)**.
- PDR thuần: điểm cuối (1.56, **1.83**) → lệch y ~1.3 m do drift.
- ⇒ ESKF **khử drift y của PDR** nhờ observation Transformer. std ≈ 0.20 m; 50 bước;
  267 update chấp nhận; **2 observation NLOS bị gating loại**.

---

## 6. Kiểm thử offline (web replay)

Mỗi khối/giai đoạn có một web test FastAPI nhẹ, phát lại CSV và vẽ quỹ đạo trên bản đồ
caro (logic vẽ giống nhau):

| Test | Cổng | Nội dung |
|---|---|---|
| `test/transformer/test_model.py` | 8036 | RSSI → Transformer → vị trí tuyệt đối |
| `test/pdr/test_pdr.py` | 8038 | IMU → PDR → dead-reckoning từ `START_CELL` |
| `test/tran_pdr_eskf/test_tran_pdr_eskf.py` | 8041 | **Toàn bộ Algorithm 3**: vẽ 3 lớp (Transformer obs, PDR-only, ESKF fused) |

Chạy ví dụ:
```powershell
.\venv\Scripts\python.exe test\tran_pdr_eskf\test_tran_pdr_eskf.py
# mở http://127.0.0.1:8041 → đổi View: All / Fused / Compare
```
Dữ liệu test (có cả RSSI lẫn IMU) ở `test/<module>/dataset/result/test_case_D8_1_1.csv`
(và D8_1_2 — có thể là quỹ đạo khác). Các entrypoint Python đều ép UTF-8 stdout để log
tiếng Việt không vỡ trên console Windows.

---

## 7. Nhúng vào trang realtime (đã hoàn thiện)

- **Runtime MQTT:** `backend/mqtt_handle/transformer_pdr_eskf/runtime.py` (`Algorithm3Runtime`)
  subscribe `reality_id/<tag>` cho từng thiết bị, nạp vào `Algorithm3Manager` (chạy 3 khối mỗi
  tag), và publish kết quả `user_pos/<tag>` mỗi khi có vị trí mới.
- **Coordinator:** `backend/algorithm_3.py` — `Algorithm3` (fusion mỗi tag) + `Algorithm3Manager`
  (quản lý nhiều tag trong một run, `SessionSimulation`, thiết bị ADMIN ảo, tọa độ hiệu chỉnh).
- **Endpoint:** `POST /api/training-alg3/{id}/start` (body `Algorithm3StartRequest`: `campaign_id`,
  `start_x/y?`, `offset_angle_bno?`, `assembly_x/y?`, `admin_enabled?`),
  `GET /api/training-alg3/{id}/state` (FE poll 700ms), `POST /api/training-alg3/{id}/admin`.
- **Trang:** `/training-live-algorithm3` (`frontend/.../training_live_algorithm3.{html,js}`) —
  hiển thị vị trí, la bàn offset, mô phỏng cháy, thiết bị ADMIN ảo (WASD/chuột).
- **Mô phỏng chữa cháy** (lan/dập lửa + tính điểm + nước): `backend/simulation/` — dùng chung với
  thuật toán 2 & 5; chi tiết + cách chỉnh tham số ở `READ_ME/Algorithm/Algorithm_simu.md`.
- **Hiệu chỉnh tham số khi chạy thật:** `offset_angle` lấy từ `maps.offset_angles` (DB);
  `offset_angle_bno` mặc định **0** ở runtime (giá trị −105 chỉ đúng cho dataset D8 — phải calib
  lại cho phần cứng thật); `WEINBERG_K`, `R_MEAS_M`, `GATING_THRESHOLD` chỉnh ở `*/config.py`.

---

## 8. Việc còn lại (roadmap)
1. **Hiệu chỉnh phần cứng thật:** đo lại `offset_angle_bno` (lệch gắn BNO) cho từng thiết bị
   (chưa lưu trong DB) và `WEINBERG_K` theo người dùng.
2. **Nâng cấp ESKF**: thêm error-state hướng `δθ`; Q/R thích nghi theo trạng thái đi
   thẳng/rẽ và vùng tin cậy của Transformer.
3. (Tùy chọn) calib `KIM_K`; xử lý D8_1_2 với start cell / quỹ đạo riêng.
