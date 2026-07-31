# PDR Module (Pedestrian Dead Reckoning)

Module này là **Khối 2** của algorithm 3: **Transformer + PDR + ESKF**.

Nhiệm vụ của PDR là biến luồng IMU (gia tốc + hướng từ BNO055) thành **vector dịch
chuyển cho mỗi bước chân** — tức mô hình chuyển động (process model). PDR **không**
tự cộng dồn vị trí; việc đó thuộc về ESKF.

```text
RSSI ──> [Transformer] ──> Z_obs = (x, y) tuyệt đối ─┐
                                                      ├─> [ESKF] ─> vị trí cuối
IMU  ──> [PDR] ──> (Δx, Δy) mỗi bước (displacement) ─┘
```

- Transformer: tọa độ tuyệt đối, không trôi nhưng nhiễu/nhảy ở vùng NLOS.
- PDR: rất mượt trong ngắn hạn nhưng **trôi (drift)** dần theo thời gian.
- ESKF: predict bằng displacement của PDR, update bằng Z_obs của Transformer.

Xem [reference_pdr.txt](reference_pdr.txt) để biết phần đối chiếu với bài báo/dự án thực tế.

---

## Cấu Trúc

```text
backend/algorithms/pdr/
  config.py        # Tham số: ngưỡng phát hiện bước, LPF, model step length, uncertainty
  pdr_model.py     # PDRModel (FSM) + _LowPassFilter + StepEvent
  reference_pdr.txt    # So sánh với literature + khuyến nghị
  READ_ME_pdr.md
```

---

## Config Trung Tâm ([config.py](config.py))

```python
# Phát hiện bước (dual-threshold trên gia tốc tuyến tính acc_z, m/s^2)
UPPER_THRESHOLD = 1.0
LOWER_THRESHOLD = -1.0
MIN_STEP_TIME = 100        # ms (khoảng đỉnh-cao -> đỉnh-thấp)
MAX_STEP_TIME = 600        # ms

# Low-pass filter khử nhiễu (IIR bậc 1). <=0 để tắt.
LOWPASS_CUTOFF_HZ = 10.0   # lọc NHẸ; dữ liệu thiết bị này sạch, cutoff thấp mất bước

# Tín hiệu phát hiện
USE_ACC_MAGNITUDE = False  # True: dùng |a|-baseline (bất biến hướng) thay acc_z

# Ước lượng chiều dài bước
STEP_LENGTH_MODEL = "weinberg"   # "fixed" | "weinberg" | "kim"
DEFAULT_STEP_LENGTH = 0.43       # fallback cho "fixed"
WEINBERG_K = 0.33                # đã calib theo dữ liệu D8 (khớp quãng đường thật)
KIM_K = 0.40
MIN_STEP_LENGTH = 0.30           # clamp
MAX_STEP_LENGTH = 1.00

# Hướng — hai mức bù góc, đều trừ khỏi yaw thô:
#   adjusted_yaw = yaw_raw - DEFAULT_OFFSET_ANGLE - DEFAULT_OFFSET_ANGLE_BNO
DEFAULT_OFFSET_ANGLE = 0.0       # góc lệch BẢN ĐỒ (từ DB). yaw_map=0 ⇒ đi +Oy
DEFAULT_OFFSET_ANGLE_BNO = 0.0   # bù lỗi GẮN BNO (luôn là bội số của 90°)

# Độ bất định cho ma trận nhiễu quá trình Q của ESKF
PROCESS_NOISE_STEP_RATIO = 0.15  # sigma_step = ratio * step_length
PROCESS_NOISE_HEADING_DEG = 3.0
```

---

## Thuật Toán ([pdr_model.py](pdr_model.py))

### 1. Low-pass filter (`_LowPassFilter`)
IIR bậc 1 (EMA) với `alpha = dt / (RC + dt)`, `RC = 1/(2π·cutoff)`, hỗ trợ dt thay
đổi (lấy từ timestamp). Khử nhiễu gia tốc tần số cao trước khi so ngưỡng.

> **Lưu ý đo thực tế (test_case_D8):** dữ liệu BNO055 của thiết bị này sạch (~65 cụm
> đỉnh rõ ràng). Cutoff thấp 3–5Hz triệt tiêu 20–35% bước thật; cutoff ~10Hz giữ
> ~85–90%. Đây là tham số nhạy — nên tinh chỉnh per-device bằng harness P1.

### 2. Phát hiện bước (FSM dual-threshold)
- Trạng thái 1: `signal > UPPER_THRESHOLD` → ghi nhận đỉnh cao, bắt đầu tích lũy
  `a_max, a_min, mean|a|` của bước.
- Trạng thái 2: tích lũy biên độ; nếu `signal < LOWER_THRESHOLD` và khoảng thời gian
  high→low ∈ [MIN_STEP_TIME, MAX_STEP_TIME] → **xác nhận bước**. Nếu quá MAX thì hủy.

`signal` = `acc_z` (mặc định) hoặc `|a| − baseline` (nếu `USE_ACC_MAGNITUDE`).

### 3. Ước lượng chiều dài bước (thích nghi)
| Model | Công thức |
|-------|-----------|
| `weinberg` | `L = WEINBERG_K · (a_max − a_min)^0.25` |
| `kim` | `L = KIM_K · (mean|a| trong bước)^(1/3)` |
| `fixed` | `L = DEFAULT_STEP_LENGTH` |

Kết quả được clamp về `[MIN_STEP_LENGTH, MAX_STEP_LENGTH]`. `K` cần **hiệu chỉnh một
lần** theo người dùng/thiết bị (đi một đoạn biết trước quãng đường để suy ra K).

### 4. Vector bước & đầu ra
```text
adjusted_yaw = yaw − offset_angle − offset_angle_bno
delta_x = L · sin(adjusted_yaw)     # dọc trục Ox của map
delta_y = L · cos(adjusted_yaw)     # dọc trục Oy của map  (adjusted_yaw=0 ⇒ +Oy)
```

**Hai mức bù góc:**
- `offset_angle` = góc lệch của BẢN ĐỒ (từ `maps.offset_angles` trong DB). Quy ước
  `yaw_map = yaw − offset_angle`, với `yaw_map=0` ⇒ đi theo +Oy. Vì vậy offset bằng
  bearing của trục +Oy. Ví dụ map 17 có **+Oy = West (270°) ⇒ offset_angle = −90**.
- `offset_angle_bno` = bù lỗi CẦM/GẮN cảm biến BNO055 (=0 nếu gắn đúng). Ban đầu giả
  định là bội số của 90°, nhưng hiệu chỉnh từ dữ liệu D8 cho **−105°** (gồm cả lệch
  gắn ~−90° lẫn lệch từ trường ~−15°), tức KHÔNG nhất thiết là bội số 90°.

> **Map 17 / D8:** Ox(5m)=North, Oy(10m)=West ⇒ `offset_angle=−90`, BNO lệch
> `offset_angle_bno=−105` (đo từ 15 bước đầu đi thẳng +Oy: yaw_raw ~164.7°). Đã kiểm
> nghiệm: quỹ đạo PDR tái tạo đúng hướng vòng tham chiếu (trục dài dọc +Oy). Phần sai
> số còn lại là drift tích lũy — giảm bằng cách hiệu chỉnh WEINBERG_K (đã set 0.33).
Mỗi bước trả về một `StepEvent`:
`timestamp, delta_x, delta_y, step_length, heading_deg, sigma_step,
sigma_heading_deg, step_index`. Trong đó `sigma_*` cung cấp cho ma trận nhiễu quá
trình Q của ESKF.

---

## Cách Dùng

```python
from backend.algorithms.pdr.pdr_model import PDRModel

# Map 17 (D8): offset_angle=-90 (Oy=West), offset_angle_bno=-105 (BNO lệch, calib từ dữ liệu)
pdr = PDRModel(offset_angle=-90.0, offset_angle_bno=-105.0, step_length_model="weinberg")
event = pdr.process_imu_stream(acc_z, yaw, timestamp_ms, acc_x, acc_y)
if event is not None:
    # đưa (event.delta_x, event.delta_y) + sigma vào ESKF predict
    ...
```

Demo nhanh:

```powershell
.\venv\Scripts\python.exe backend\algorithms\pdr\pdr_model.py
```

---

## Kết Quả Kiểm Chứng & Hiệu Chỉnh (test_case_D8_1_1, phát lại offline)

Map 17/D8: `offset_angle=-90` (Oy=West), `offset_angle_bno=-105` (đo từ 15 bước đầu
đi thẳng +Oy, yaw_raw ~164.7°), `WEINBERG_K=0.33`, LPF 10Hz, 50 bước.

Hiệu chỉnh K theo TỔNG QUÃNG ĐƯỜNG (độc lập với hướng):
```text
Chiều dài quỹ đạo tham chiếu (center-to-center) = 24.41 m
K=0.40 -> PDR = 29.48 m (overshoot ~21%);  D8_1_1 -> K=0.331, D8_1_2 -> K=0.320
K=0.33 -> PDR = 24.32 m  (sai số 0.4% so với 24.41 m)  ✓
```

Kết quả với tham số đã calib: điểm cuối x≈1.56 (cell 2 thật =1.5), x-range[0.4,4.8],
y-range[0.5,9.9] — khớp đẹp với map 5×10. Lệch y cuối ~1.3m là **drift hướng tích
lũy còn lại** (từ trường + nhiễu mỗi bước), sẽ được **ESKF (Khối 3) sửa** bằng
observation tuyệt đối của Transformer.

> Lưu ý: `offset_angle_bno=-105` và `WEINBERG_K=0.33` là thuộc tính NGƯỜI/THIẾT BỊ
> (calib 1 lần), không phụ thuộc map. `offset_angle` mới là thuộc tính map (từ DB).

---

## Giới Hạn & Việc Còn Lại

- **Drift hướng:** dựa hoàn toàn vào yaw BNO055; nhiễu từ trường trong nhà có thể
  lệch hướng. ESKF (observation vị trí) khó sửa trực tiếp hướng.
- **Hiệu chỉnh K:** `WEINBERG_K`/`KIM_K` cần calib theo người (mặc định đã set 0.33 từ D8).
- **Đã tích hợp:** ESKF (Khối 3) + điều phối `algorithm_3.py` (`Algorithm3`/`Algorithm3Manager`)
  + runtime MQTT (`mqtt_handle/transformer_pdr_eskf/`) đều đã hoàn thiện và chạy real-time. Lưu ý:
  `offset_angle_bno` mặc định 0 ở runtime (giá trị −105 chỉ đúng cho bộ dữ liệu D8).
- **Harness test P1:** `test/pdr/test_pdr.py` (web offline replay, dữ liệu trong
  `test/pdr/dataset/result/`) — tương tự `test/transformer/test_model.py`.
```
