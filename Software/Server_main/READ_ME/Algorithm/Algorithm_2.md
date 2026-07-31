# Thuật Toán 2 — UWB Trilateration: Robust LM (loosely-coupled)

Tài liệu chi tiết cho **developer** về thuật toán định vị số 2. Đây là thuật toán định vị
**2D từ khoảng cách UWB** tới các anchor (beacon), theo kiểu **loosely-coupled**: giải ra
**toạ độ** trước (bình phương tối thiểu robust), rồi mới làm mượt bằng Kalman tuyến tính.

> Tài liệu code & lý thuyết chi tiết của từng phần:
> - Mô tả module (dev): `backend/algorithms/trilateration_LM/READ_ME_tri_lm.md`
> - Đối chiếu khoa học + nguồn: `backend/algorithms/trilateration_LM/reference_tri_lm.txt`
> - Mô phỏng chữa cháy (dùng chung algo 2/3/5): `READ_ME/Algorithm/Algorithm_simu.md`
> - Truyền thông MQTT: `READ_ME/Comunicate/MQTT.md`
>
> Thuật toán 5 (UWB tightly-coupled EKF) là "anh em song sinh" dùng chung pipeline realtime —
> xem `READ_ME/Algorithm/Algorithm_5.md`.

---

## 1. Tổng quan & trạng thái

- **Đầu vào:** các khoảng cách UWB thô (cm, chưa lọc) từ tag tới ≥3 anchor (gồm ≥1 master).
- **Đầu ra:** toạ độ `(x, y)` đã làm mượt + vận tốc `(vx, vy)`.
- **Chỉ dùng UWB** (không IMU/PDR). Dữ liệu **không có CIR** → chống NLoS bằng residual
  (Huber) + trọng số WLS, không bằng CIR.
- **Trạng thái: hoàn thiện real-time** — đã có runtime MQTT + trang `/training-live-algorithm2`
  (bản sao trang algo 3) + mô phỏng chữa cháy. Kiểm chứng offline (4 anchor mô phỏng); chưa có
  dataset UWB thật nên tham số đặt theo literature, cần calib khi có log thật.

Điều kiện bật thuật toán cho một map: **≥3 UWB beacon gồm ≥1 UWB master** (giống algo 5;
`UWB_ALGORITHMS=(2,5)` trong `main.py`).

---

## 2. Kiến trúc (loosely-coupled, 4 bước)

```
range thô (cm) ─► cm→m + clamp [0.10, 30.0] m
              ─► Kalman khoảng cách / anchor (distance_kalman.py)      # Bước 0
              ─► LLS seed (engine.lls_initial_position)                # Bước 1
              ─► LM robust (engine.solve_trilateration_robust):        # Bước 2
                   λ adaptive + IRLS-Huber + WLS  ─► (x, y) + covariance P
              ─► Constant-Velocity Kalman (position_kf.py, R∝P)        # Bước 3
                   ─► (x, y) mượt + (vx, vy)
```

"Loosely-coupled" = tầng LS cho ra **vị trí**, nên bộ lọc cuối chỉ cần **Kalman tuyến tính
vận tốc-hằng (CV)** — KHÔNG cần EKF (EKF là đường tightly-coupled của algo 5).

**Các file:**
- `backend/algorithm_2.py` — `Algorithm2` (file chủ, điều phối 4 bước cho MỘT tag).
- `backend/algorithms/trilateration_LM/engine.py` — `lls_initial_position` +
  `solve_trilateration_robust` (LM λ-adaptive + IRLS-Huber + WLS, trả covariance `P`).
- `.../distance_kalman.py` — Kalman 1D từng anchor (gate bỏ-update / re-acquire).
- `.../position_kf.py` — `ConstantVelocityKF` `[x,y,vx,vy]`, R thích nghi theo `P`.
- (legacy, không dùng cho code mới: `positioning.py`, `user_state.py`,
  `solve_trilateration_lm` — chỉ phục vụ trang `/training-live-trilateration` cũ.)

---

## 3. Chi tiết thuật toán (tóm tắt — chi tiết ở READ_ME_tri_lm.md)

- **LLS seed:** trừ phương trình của anchor gần nhất → hệ tuyến tính `A·p=b`, giải đóng → điểm
  khởi tạo cho LM (LM rất nhạy điểm khởi tạo).
- **LM robust:** tối thiểu hoá `Σ Wᵢ(‖p−aᵢ‖−dᵢ)²`; `Wᵢ = prior_weightᵢ · Huber(residualᵢ)`;
  **λ adaptive** (cost giảm → nhận bước + giảm λ; cost tăng → loại bước + tăng λ). Trả covariance
  hình học `P = pinv(JᵀWJ)` (lớn khi GDOP xấu).
- **Kalman khoảng cách (Bước 0):** mỗi anchor một bộ lọc random-walk; gate `|z−x⁻|`: vượt → **bỏ
  update** (giữ prediction, để P phình) — KHÔNG "clamp về prediction" (antipattern đã sửa); bị từ
  chối liên tiếp ≥N → **re-acquire**. `variance(hex)` dùng làm trọng số WLS ≈ 1/variance.
- **CV Kalman (Bước 3):** `R = CV_RANGE_STD_M² · P_geom` (kẹp `[floor², ceil²]`) → vùng hình học
  xấu được tin ít hơn.

---

## 4. Tham số & cách hiệu chỉnh

Tham số nằm ở **đầu mỗi file** (dễ chỉnh):
- `algorithm_2.py`: `RANGE_MIN_M=0.10`, `RANGE_MAX_M=30.0`, `MIN_BEACONS=3`,
  `USE_DISTANCE_KALMAN=True`, `USE_WLS_PRIOR=True`, `WARM_START=True`.
- `engine.py`: `LM_MAX_ITER=20`, `LM_INITIAL_LAMBDA=1e-2`, `LM_LAMBDA_DOWN=0.7`,
  `LM_LAMBDA_UP=2.5`, `LM_CONVERGENCE_STEP_M=1e-4`, `HUBER_DELTA_M=0.5`.
- `distance_kalman.py`: `DEFAULT_PROCESS_VARIANCE=0.02`, `DEFAULT_MEASUREMENT_VARIANCE=0.04`
  (σ≈0.2m), `DEFAULT_INNOVATION_GATE_M=1.0`, `DEFAULT_REACQUIRE_AFTER=3`.
- `position_kf.py`: `CV_PROCESS_PSD=1.5`, `CV_RANGE_STD_M=0.20`, `CV_MEAS_STD_FLOOR_M=0.08`,
  `CV_MEAS_STD_CEIL_M=1.50`.

> Hướng hiệu chỉnh khi có log UWB thật: đặt `CV_RANGE_STD_M`/`DEFAULT_MEASUREMENT_VARIANCE` theo σ
> range LoS đo được (≈0.05–0.2m); chỉnh `HUBER_DELTA_M` theo mức bias NLoS; tăng `CV_PROCESS_PSD`
> nếu bám chuyển động chậm.

---

## 5. Kết quả kiểm chứng (synthetic 4 anchor)

| Kịch bản | Sai số vị trí |
|---|---|
| LoS sạch | ≈ 0.05 m |
| 1 anchor NLoS +1.5 m | ≈ 0.35 m (Huber giảm trọng số anchor lệch) |
| Mục tiêu di chuyển | ≈ 0.07 m |

**Trần 4-anchor:** chỉ loại bền vững tối đa **1** anchor NLoS; ≥2 range lệch thì không cứu được.
**2D:** giả thiết anchor/tag đồng phẳng (lệch độ cao gây bias range).

---

## 6. Nhúng vào trang realtime (đã hoàn thiện)

- **Pipeline dùng chung với algo 5:** coordinator `backend/algorithm_uwb.py` (`UWBManager`) +
  runtime `backend/mqtt_handle/trilateration_uwb/runtime.py` (`UWBRuntime`); bộ não chọn theo
  `run["algorithm"]` (=2 → `Algorithm2`). Là bản sao cấu trúc của `Algorithm3Manager`.
- **Nhận (MQTT):** ranging `2/uwb_ranging/<master>/<slave>` (payload `<tag>,<dist_cm>,...`, gom
  theo slave) + `uwb_id/<tag>` (IMU/valve — chỉ cho FOV + mô phỏng, KHÔNG định vị).
- **Gửi (MQTT):** `user_pos/<tag>` + `fire_data` — **giống hệt algo 3**.
- **Endpoint:** `POST /api/training-alg2/{id}/start` (body `UWBStartRequest`: start_x/y?,
  assembly_x/y?, admin_enabled?), `GET /api/training-alg2/{id}/state` (FE poll 700ms),
  `POST /api/training-alg2/{id}/admin`.
- **Trang:** `/training-live-algorithm2` (`training_live_algorithm2.{html,js}`) — bản sao y hệt
  trang algo 3 (4 vùng, la bàn offset, mô phỏng cháy, thiết bị ADMIN ảo); chỉ khác backend định vị.
  Panel chẩn đoán hiển thị "Beacons used" + **RMS error**.
- **State** mỗi tag: `position_x/y`, `cell_index`, `yaw_raw/map`, `valve_open/mode`, `spray_mode`,
  `num_beacons`, `rms_error`, `score`, `water_remaining`/`water_capacity`, `fires_extinguished`,
  `disqualified`; kèm tag ADMIN + `fires`/`root_fires`/`ended`/`outcome`.

---

## 7. Việc còn lại
- Hiệu chỉnh tham số (Kalman/LM) từ log UWB thật khi có (hiện dùng giá trị literature).
- Bảo đảm có ≥3 range thật khi triển khai phần cứng (range hiện về theo topic **slave**; kiểm tra
  master cũng ranging hoặc bố trí ≥3 slave).

> **Lưu ý legacy:** trang `/training-live-trilateration` + `mqtt_handle/trilateration_LM/runtime.py`
> + `positioning.py`/`user_state.py` là bản algo-2 cũ, còn chạy nhưng KHÔNG còn liên kết từ
> training-select. Không dùng cho code mới.
