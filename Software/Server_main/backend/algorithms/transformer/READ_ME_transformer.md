# RSSI Transformer Module

Module này là **Khối 1** của algorithm 3: **Transformer + PDR + ESKF**.

Nhiệm vụ của Transformer là học bản đồ fingerprint RSSI tĩnh từ 8 kênh đầu vào:

- `wifi_rssi_1..4`
- `ble_rssi_1..4`

Đầu ra là tọa độ tuyệt đối `(x, y)` theo mét.

Transformer **không** quyết định vị trí cuối cùng của hệ thống. Kiến trúc tổng thể:

```text
Transformer observation -> ESKF fusion <- PDR motion prediction
```

ESKF là tầng fusion cuối, dùng quán tính từ PDR để giảm các bước nhảy sai số của
Transformer ở vùng biên, góc khuất hoặc vùng NLOS nặng.

---

## Cấu Trúc

```text
backend/algorithms/transformer/
  config.py
  READ_ME_transformer.md
  reference_transformer.txt  # So sánh với paper/dự án thực tế + khuyến nghị
  training/
    preprocess.py            # Lọc dữ liệu + temporal split + scaler + sliding window
    dataset.py               # Đóng gói DataLoader
    model_def.py             # PositionalEncoding + RSSITransformer
    train.py                 # Train loop (AdamW + early stopping) + auto eval/plot
    evaluate.py              # Sai số vật lý (m) trên test split
    visualize.py             # Vẽ biểu đồ loss (thay cho draw.py cũ)
  model/
    map_{MAP_ID}/
      campaign_{CAMPAIGN_ID}/
        scaler.joblib                       # MinMaxScaler fit TRÊN TRAIN
        transformer_model.pt                # Best checkpoint theo val loss
        train_{N}_epochs_stdout.log         # Log từng epoch (tự ghi)
        training_history.csv                # epoch, train_loss, val_loss, is_best
        evaluation_metrics.json             # mean/median/max/CE90 (m)
        evaluation_predictions.csv
        evaluation_coordinate_errors.csv
        loss_analysis_comprehensive.png     # 9 subplot phân tích loss
        loss_statistics.png                 # 4 subplot thống kê
        loss_data.csv
```

Hiện có 2 lần train: `model/map_15/campaign_14/` (pipeline CŨ) và
`model/map_17/campaign_18/` (pipeline MỚI — bản tham chiếu hiện tại).

---

## Config Trung Tâm

File [config.py](config.py) là nguồn chân lý duy nhất cho mọi tham số:

```python
# Dữ liệu
MAP_ID = 17
CAMPAIGN_ID = 18
SAMPLES_PER_CELL = 500

# Lọc RSSI: chỉ giữ mẫu có cả 8 kênh trong dải hợp lệ [-99, -1] dBm.
RSSI_VALID_MIN = -99
RSSI_VALID_MAX = -1
NULL_RSSI_VALUE = -100      # giữ để tương thích cũ, không còn dùng để điền sentinel

# Cửa sổ thời gian
WINDOW_SIZE = 35            # ~1 giây ở 35Hz
STEP_SIZE = 5

# Training
BATCH_SIZE = 64
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15
LEARNING_RATE = 0.001
EPOCHS = 100                # TRẦN; early stopping có thể dừng sớm hơn
RANDOM_SEED = 42
WEIGHT_DECAY = 1e-4         # L2 cho AdamW
EARLY_STOP_PATIENCE = 12    # dừng nếu val loss không cải thiện 12 epoch liên tiếp
EARLY_STOP_MIN_DELTA = 1e-4
SPLIT_STRATEGY = "temporal" # chia theo thời gian trong từng cell (chống rò rỉ)

# Kiến trúc
INPUT_DIM = 8
D_MODEL = 64
N_HEADS = 4
NUM_LAYERS = 2
OUTPUT_DIM = 2
DROPOUT = 0.1
```

Artifact lưu tự động theo `model/map_{MAP_ID}/campaign_{CAMPAIGN_ID}/`.

---

## Task 1 — Tiền xử lý dữ liệu ([training/preprocess.py](training/preprocess.py))

- Đọc `.env`, kết nối MySQL `indoor_positioning_db`.
- JOIN `fingerprint_data` với `map_cells` theo `MAP_ID`, `CAMPAIGN_ID`.
- Chỉ dùng 8 kênh RSSI Wi-Fi/BLE (không dùng magnetometer để tránh lỗi xoay thiết bị).
- Sort theo `cell_id`, `collected_at`, `fingerprint_id`.
- **Lọc dữ liệu lỗi (`_drop_invalid_rssi_rows`)**: loại bỏ HOÀN TOÀN mọi dòng có bất
  kỳ kênh RSSI nào null/NaN hoặc nằm ngoài `[RSSI_VALID_MIN, RSSI_VALID_MAX] = [-99, -1]`
  (mất tín hiệu ≤ -100, hoặc giá trị dương do lỗi cảm biến). Không điền sentinel.
- **Chia train/val/test theo THỜI GIAN trong từng cell** (`SPLIT_STRATEGY="temporal"`):
  mẫu thu sớm → train, giữa → val, muộn → test. 3 đoạn không chồng thời gian.
- **Fit `MinMaxScaler` CHỈ trên train**, transform val/test, lưu `scaler.joblib`.
- Tạo sliding window theo từng cell, riêng từng split (không vắt ngang cell, không
  vắt ngang split).
- Entrypoint chính: **`get_split_windows()`** → trả về `((X_train,y_train),(X_val,y_val),(X_test,y_test))`.

> Vì sao temporal split thay cho random split: window kề nhau chồng lấn 86% và mọi
> mẫu trong 1 cell là cùng vị trí (chỉ khác nhiễu). Random shuffle khiến train/test
> gần như trùng → sai số đánh giá LẠC QUAN giả tạo. Temporal split mô phỏng đúng tình
> huống đo ở thời điểm khác → con số trung thực hơn. Chi tiết trong `reference_transformer.txt`.

Lệnh test:

```powershell
.\venv\Scripts\python.exe backend\algorithms\transformer\training\preprocess.py
```

Kết quả trên map_17/campaign_18 (đã kiểm tra):

```text
[preprocess] Loại 294/23500 mẫu RSSI không hợp lệ (null hoặc ngoài [-99, -1]); còn 23206 mẫu hợp lệ.
Train X shape: (2975, 35, 8)
Val   X shape: (403, 35, 8)
Test  X shape: (416, 35, 8)
```

---

## Task 1b — Dataset Loader ([training/dataset.py](training/dataset.py))

- Gọi `get_split_windows()` (đã chia sẵn theo thời gian).
- Convert sang `torch.float32`, đóng gói `TensorDataset` + `DataLoader`.
- Chỉ `train_loader` shuffle; val/test giữ nguyên thứ tự.

---

## Task 2 — Model ([training/model_def.py](training/model_def.py))

`PositionalEncoding` + `RSSITransformer`:

```text
[Batch, 35, 8]
  -> Linear(8, 64)
  -> Positional Encoding (sinusoidal)
  -> Transformer Encoder (2 layers, 4 heads, ff=256, dropout=0.1)
  -> Mean Pooling over time
  -> Linear(64, 32) -> ReLU -> Linear(32, 2)
  -> [Batch, 2]
```

~102,690 tham số — đủ nhẹ để inference CPU real-time.

---

## Task 3 — Training ([training/train.py](training/train.py))

- Tự chọn device (CUDA/MPS/CPU).
- Loss `nn.MSELoss`; optimizer **`AdamW(lr=1e-3, weight_decay=1e-4)`**.
- **Early stopping theo patience** (dừng nếu val loss không cải thiện
  `EARLY_STOP_PATIENCE` epoch); `EPOCHS` chỉ là trần. Best checkpoint theo val loss
  luôn được giữ → model lưu KHÔNG dính phần overfit ở cuối.
- **Tự động** ghi `train_{N}_epochs_stdout.log` + `training_history.csv`, rồi chạy
  `evaluate.py` và `visualize.py` ở cuối (tắt bằng `--no-eval` / `--no-plot`).
  Nhờ vậy mọi campaign luôn có đủ artifact, không phụ thuộc redirect/script thủ công.

Lệnh:

```powershell
# Train (EPOCHS làm trần, early stopping tự dừng)
.\venv\Scripts\python.exe backend\algorithms\transformer\training\train.py --epochs 200

# Smoke test ngắn
.\venv\Scripts\python.exe backend\algorithms\transformer\training\train.py --epochs 1
```

Kết quả map_17/campaign_18 (đã kiểm tra): early stopping dừng ở **epoch 47**,
**Best Val Loss = 0.888186 (epoch 35)**. Quan hệ: `RMS(m) = sqrt(2 × val_loss)`.

---

## Task 4 — Evaluation ([training/evaluate.py](training/evaluate.py))

Tính sai số Euclid vật lý theo mét `sqrt((x_pred-x_true)^2 + (y_pred-y_true)^2)`,
lưu `evaluation_metrics.json` + 2 CSV. Tự chạy ở cuối train (hoặc chạy tay).

Kết quả map_17/campaign_18 (temporal split — trung thực):

```text
Mean Error:   1.206 m
Median Error: 1.023 m
Max Error:    4.995 m
CE90:         2.153 m
```

> So sánh: map_15 cũ đạt 0.422 m nhưng dùng random split (có rò rỉ) nên LẠC QUAN.
> 1.206 m mới là độ chính xác THẬT của observation model. Lỗi cao tập trung ở các ô
> rìa/góc (NLOS) — đây chính là phần ESKF + PDR sẽ làm mượt.

---

## Task 5 — Visualization ([training/visualize.py](training/visualize.py))

Thay cho `draw.py` cũ (vốn nằm lạc trong thư mục model và phụ thuộc `seaborn` chưa cài).
Đọc `training_history.csv` (fallback parse log), vẽ `loss_analysis_comprehensive.png`
+ `loss_statistics.png` + `loss_data.csv`. Không phụ thuộc seaborn, chạy headless (Agg).

---

## Artifact Runtime Dùng (đã hoàn thiện)

```text
scaler.joblib        # load, TUYỆT ĐỐI không fit lại
transformer_model.pt # best checkpoint
```

Runtime đã chạy thật trong `backend/algorithm_3.py` (`Algorithm3`/`Algorithm3Manager`) thông qua
handler MQTT `backend/mqtt_handle/transformer_pdr_eskf/runtime.py` (sub `reality_id`, pub
`user_pos`). Luồng:

```text
MQTT RSSI stream (reality_id/<tag>)
  -> lọc dòng có RSSI ngoài [-99,-1] (skip, không nạp model — giống training)
  -> build sliding window [1, 35, 8]
  -> load scaler.joblib + transform (clip về [0,1])
  -> RSSITransformer inference -> observation [x_obs, y_obs]
  -> ESKF update (kết hợp với displacement từ PDR)
```

---

## Lưu Ý Kỹ Thuật

- **Lọc RSSI [-99, -1] là quy tắc chung** cho cả training (preprocess) lẫn runtime/test
  (`test/transformer/test_model.py`): dòng có giá trị ngoài dải → bỏ qua, không nạp model.
- `scaler.joblib` fit CHỈ trên train (không còn fit trên toàn bộ dữ liệu).
- Encoding: các entrypoint ép UTF-8 cho stdout/stderr (`_enable_utf8_console`) để log
  tiếng Việt không vỡ trên console Windows (cp1252).
- Console output của vòng train dùng tiếng Anh ASCII để tương thích; log file là UTF-8.
- Transformer chỉ là observation model; các cú nhảy sai số ở vùng NLOS sẽ được ESKF xử
  lý bằng motion constraint từ PDR.
```
