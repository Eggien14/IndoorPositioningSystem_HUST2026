# Trilateration LM — Thuật toán 2 (Robust LM, loosely-coupled)

Module này là **Thuật toán 2**: định vị tag trong 2D từ **khoảng cách UWB tới các anchor**
(beacon), theo kiểu **loosely-coupled** — giải ra **vị trí** trước, rồi mới lọc.

> "Loosely-coupled" = tầng bình phương tối thiểu (LS) cho ra một **toạ độ (x, y)**, nên bộ
> lọc cuối chỉ cần là **Kalman tuyến tính vận tốc-hằng (CV)**, KHÔNG cần EKF. Bản tightly-coupled
> (nạp thẳng range vào EKF) là **Thuật toán 5** — xem `../trilateration_ekf/READ_ME_tri_ekf.md`.

Chỉ dùng **UWB** (không IMU/PDR). Dữ liệu KHÔNG có CIR → chống NLoS bằng **residual** (Huber +
trọng số WLS), không phải bằng CIR. Phần đối chiếu nguồn khoa học: [reference_tri_lm.txt](reference_tri_lm.txt)
(mục 1-11). Tóm tắt cho AI agent: [`../CLAUDE_algor2.md`](../CLAUDE_algor2.md).

```text
range thô (cm) ─► cm→m + clamp [0.10, 30.0] m
              ─► Kalman khoảng cách / anchor (distance_kalman)        # Bước 0
              ─► LLS seed  (engine.lls_initial_position)              # Bước 1
              ─► LM robust (engine.solve_trilateration_robust):       # Bước 2
                   λ adaptive + IRLS-Huber + WLS  ─► (x, y) + covariance P
              ─► Constant-Velocity Kalman vị trí (position_kf, R∝P)   # Bước 3
                   ─► (x, y) mượt + (vx, vy)
```

---

## Cấu Trúc

```text
backend/algorithms/trilateration_LM/
  engine.py          # Bộ giải hình học: lls_initial_position + solve_trilateration_robust (+ solve_trilateration_lm CŨ)
  distance_kalman.py # Kalman 1D từng anchor (random-walk) + gate bỏ-update/re-acquire
  position_kf.py     # ConstantVelocityKF [x,y,vx,vy], R thích nghi theo P
  positioning.py     # (CŨ) TrilaterationPositioning — chỉ cho trang algo-2 LEGACY, đừng dùng mới
  user_state.py      # (CŨ) UserStateTracker — chỉ cho runtime legacy
  reference_tri_lm.txt   # Đối chiếu literature + quyết định triển khai
  READ_ME_tri_lm.md

backend/algorithm_2.py   # File CHỦ: class Algorithm2 — điều phối 4 bước cho MỘT tag
```

> File chủ `Algorithm2` nằm ở `backend/algorithm_2.py` (cùng cấp `algorithm_3.py`), không nằm
> trong thư mục này. Tầng MQTT realtime (`UWBManager` + `UWBRuntime`) dùng `Algorithm2` —
> xem `backend/algorithm_uwb.py` và `backend/mqtt_handle/trilateration_uwb/`.

---

## 1. `engine.py` — Bộ giải hình học

**Tham số ở đầu file:**
```python
MIN_BEACONS = 3              # số anchor tối thiểu cho fix 2D
LM_MAX_ITER = 20             # số vòng lặp LM tối đa
LM_INITIAL_LAMBDA = 1e-2     # damping λ khởi tạo
LM_LAMBDA_DOWN = 0.7         # cost giảm → λ *= (nhận bước, tiến về Gauss-Newton)
LM_LAMBDA_UP   = 2.5         # cost tăng → λ *= (loại bước, tiến về gradient descent)
LM_LAMBDA_MIN  = 1e-7
LM_LAMBDA_MAX  = 1e7
LM_CONVERGENCE_STEP_M = 1e-4 # |step| < ngưỡng → hội tụ
HUBER_DELTA_M  = 0.5         # ngưỡng residual robust (m)
```

### `lls_initial_position(points, distances) -> np.ndarray | None`
Linearized Least Squares **dạng đóng** → điểm khởi tạo `(x, y)`. Trừ phương trình của anchor
**tham chiếu** (chọn anchor **gần nhất** ~ dễ LoS) để khử số hạng `x²+y²`, đưa về hệ tuyến tính
`A·p = b`, giải OLS bằng `np.linalg.lstsq`. Trả `None` nếu suy biến. Đây là "hạt giống" để LM
không phân kỳ (LM lặp rất nhạy với điểm khởi tạo).

### `solve_trilateration_robust(beacon_positions, tag_distances_m, prior_weights=None, initial_guess=None, huber_delta=0.5, max_iter=20) -> dict | None`
Damped-LM với **λ adaptive** tối thiểu hoá `Σ Wᵢ (‖p − aᵢ‖ − dᵢ)²`:
- **Jacobian** mỗi anchor: `Jᵢ = (p − aᵢ) / ‖p − aᵢ‖`.
- **Trọng số** `Wᵢ = prior_weightᵢ · Huber(residualᵢ)` với `Huber`: `|r| ≤ δ → 1`, ngược lại `δ/|r|`
  (IRLS — anchor lệch nhiều bị giảm trọng số → chịu được 1 anchor NLoS).
- **λ adaptive**: cost giảm → nhận bước, `λ *= LM_LAMBDA_DOWN` (về Gauss-Newton); cost tăng →
  loại bước, `λ *= LM_LAMBDA_UP` (về gradient descent). An toàn hơn Gauss-Newton thuần.
- **Điểm khởi tạo**: `initial_guess` (warm-start) → nếu không có dùng `lls_initial_position` →
  cuối cùng dùng centroid.
- **Covariance hình học** `P = pinv(JᵀWJ)` — lớn khi GDOP xấu / trọng số nhỏ → đưa xuống bước 3
  làm `R` thích nghi.

Trả: `{x, y, P (2×2 np.ndarray), rms, residuals{hex:r}, num_beacons}`.

### `solve_trilateration_lm(...)` — **GIỮ NGUYÊN, đừng dùng cho việc mới**
Bản damped Gauss-Newton **không trọng số** (12 vòng) của đường chạy CŨ (`positioning.py` +
trang `/training-live-trilateration` legacy). Để lại để trang cũ vẫn chạy; code mới dùng
`solve_trilateration_robust`.

---

## 2. `distance_kalman.py` — Kalman khoảng cách từng anchor

**Tham số ở đầu file:**
```python
DEFAULT_PROCESS_VARIANCE     = 0.02   # Q (m²/bước) — cho range "trôi" theo chuyển động
DEFAULT_MEASUREMENT_VARIANCE = 0.04   # R (m²); σ≈0.2 m LoS → R≈0.04
DEFAULT_INITIAL_ERROR_VARIANCE = 1.0  # P0 (m²)
DEFAULT_INNOVATION_GATE_M    = 1.0    # gate |z − x⁻| (m); vượt → BỎ update
DEFAULT_REACQUIRE_AFTER      = 3      # bị từ chối liên tiếp ≥ N lần → nhận lại (range nhảy bậc)
```

Mỗi cặp (tag, anchor) một bộ lọc **random-walk** 1D (`ScalarKalmanDistanceFilter`), gom trong
`DistanceKalmanFilterBank` (chéo độc lập). API: `.filter(hex, dist_m) → float|None`,
`.variance(hex)`, `.reset()`, `.snapshot()`.

> **LỖI ĐÃ SỬA (quan trọng — xem reference_tri_lm.txt mục 4):** bản cũ khi `|innovation| > gate` thì
> **"clamp measurement về prediction"** — vừa làm filter **quá tự tin** (P không phình), vừa
> khiến nó **dính/trễ** và bỏ qua chuyển động thật. Bản mới: gate fail → **BỎ update** (giữ
> prediction, để P phình ra); nếu bị từ chối **liên tiếp ≥ `REACQUIRE_AFTER`** → coi là range
> nhảy bậc thật (người dùng di chuyển nhanh) → **RE-ACQUIRE** (nhận lại measurement).

`variance(hex)` (P hiện tại của anchor) được `Algorithm2` dùng làm trọng số WLS `≈ 1/variance`.

---

## 3. `position_kf.py` — `ConstantVelocityKF`

**Tham số ở đầu file:**
```python
CV_PROCESS_PSD      = 1.5    # q: mật độ phổ gia tốc (m²/s³). Lớn → bám nhanh, kém mượt
CV_RANGE_STD_M      = 0.20   # σ range (m) để quy P_geom → covariance vị trí
CV_MEAS_STD_FLOOR_M = 0.08   # chặn dưới σ đo (m)
CV_MEAS_STD_CEIL_M  = 1.50   # chặn trên σ đo (m)
CV_INIT_POS_VAR     = 4.0    # P0 vị trí (m²)
CV_INIT_VEL_VAR     = 1.0    # P0 vận tốc (m²/s²)
CV_MAX_DT_S         = 1.0    # chặn dt (giây) tránh nhảy lớn khi mất nhịp
CV_DEFAULT_DT_S     = 0.1    # dt mặc định khi không cấp
```

State `[x, y, vx, vy]` (vận tốc-hằng, white-noise-acceleration). Đo `(x, y)` từ tầng LS →
`H` tuyến tính → **KF tuyến tính là đủ**. `update(z_xy, dt, meas_cov) → (x, y)`; `.velocity`;
`.reset()`.

- `Q(dt)` = ma trận white-noise-acceleration chuẩn theo `CV_PROCESS_PSD`.
- **R thích nghi**: `R = CV_RANGE_STD_M² · P_geom` (P_geom = covariance solver trả ở bước 2),
  chặn đường chéo vào `[floor², ceil²]` → fix ở vùng hình học xấu (GDOP lớn) sẽ ÍT được tin hơn.

---

## 4. `backend/algorithm_2.py` — File chủ `Algorithm2`

**Tham số ở đầu file:**
```python
RANGE_MIN_M = 0.10          # loại range quá nhỏ
RANGE_MAX_M = 30.0          # loại range quá lớn
MIN_BEACONS = 3             # số anchor tối thiểu để giải
USE_DISTANCE_KALMAN = True  # bật Kalman từng anchor (Bước 0)
USE_WLS_PRIOR = True        # trọng số WLS = 1/variance (chuẩn hoá mean≈1)
WARM_START = True           # dùng vị trí lần trước làm điểm khởi tạo LM
```

- `Algorithm2(beacon_positions: Dict[hex, (x, y)])` — hex chuẩn hoá `0x..` thường.
- `process_ranges(raw_distances_cm: Dict[hex, cm], dt: float|None) -> dict | None`:
  lọc range → Kalman/anchor → WLS prior → `solve_trilateration_robust` → `ConstantVelocityKF`.
  Trả `{x, y, raw_x, raw_y, rms_error, num_beacons, residuals_m, velocity, filtered_distances_cm}`
  (`x,y` = đã lọc CV; `raw_x,raw_y` = nghiệm hình học trước lọc). `reset()`.

---

## 5. Lưu Ý & Giới Hạn

- **UWB-only**, không IMU/PDR; `uwb_id` (yaw/valve) chỉ phục vụ FOV + mô phỏng lửa ở tầng web.
- **Không CIR** → trọng số NLoS dựa hoàn toàn vào residual (Huber) + WLS.
- **Trần 4-anchor**: chỉ loại được tối đa **1** anchor NLoS một cách bền vững; nếu ≥2 range bị
  lệch thì không cứu được (thiếu dư thừa hình học).
- **2D**: giả thiết anchor/tag ~ đồng phẳng (không z); lệch độ cao sẽ làm range bị thiên.
- **Chưa có dataset UWB thật** (`test/uwb/uwb_fakedata_test.py` = giả) → tham số theo literature
  (σ_LoS ≈ 0.05–0.2 m); cần **hiệu chỉnh lại** `R`, gate, λ, `HUBER_DELTA_M`, PSD khi có log thật.

## 6. Số Liệu Kiểm Chứng (synthetic 4 anchor)

| Kịch bản | Sai số vị trí |
|---|---|
| LoS sạch | ≈ **0.05 m** |
| 1 anchor NLoS +1.5 m | ≈ **0.35 m** (Huber giảm trọng số anchor lệch) |
| Mục tiêu di chuyển | ≈ **0.07 m** |

(So sánh: Thuật toán 5 / EKF gate hẳn anchor NLoS → ≈ 0.04 m. Xem `../trilateration_ekf/READ_ME_tri_ekf.md`.)
