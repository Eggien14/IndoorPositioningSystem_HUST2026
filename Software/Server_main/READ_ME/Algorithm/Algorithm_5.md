# Thuật Toán 5 — UWB Trilateration: Tightly-coupled EKF

Tài liệu chi tiết cho **developer** về thuật toán định vị số 5. Đây là thuật toán định vị
**2D từ khoảng cách UWB**, theo kiểu **tightly-coupled**: nạp **range thô** trực tiếp vào MỘT
bộ Extended Kalman Filter (EKF), không qua bước giải bình phương tối thiểu riêng.

> Tài liệu code & lý thuyết chi tiết:
> - Mô tả module (dev): `backend/algorithms/trilateration_ekf/READ_ME_tri_ekf.md`
> - Đối chiếu khoa học + nguồn: `backend/algorithms/trilateration_ekf/reference_tri_ekf.txt`
>   (+ nguồn chung `backend/algorithms/trilateration_LM/reference_tri_lm.txt`)
> - Mô phỏng chữa cháy (dùng chung algo 2/3/5): `READ_ME/Algorithm/Algorithm_simu.md`
> - Truyền thông MQTT: `READ_ME/Comunicate/MQTT.md`
>
> Thuật toán 2 (UWB loosely-coupled Robust LM) là "anh em song sinh" dùng chung pipeline
> realtime — xem `READ_ME/Algorithm/Algorithm_2.md`.

---

## 1. Tổng quan & trạng thái

- **Đầu vào:** các khoảng cách UWB thô (cm, chưa lọc) từ tag tới các anchor.
- **Đầu ra:** toạ độ `(x, y)` + vận tốc `(vx, vy)`.
- **Chỉ dùng UWB** (không IMU/PDR). Không có CIR → chống NLoS bằng **gate NIS/Mahalanobis + Huber**
  trên từng range.
- **Trạng thái: hoàn thiện real-time** — runtime MQTT + trang `/training-live-algorithm5` (bản sao
  trang algo 3) + mô phỏng chữa cháy. Kiểm chứng offline (4 anchor mô phỏng); chưa có dataset UWB
  thật → tham số theo literature, calib khi có log thật.

Điều kiện bật: **≥3 UWB beacon gồm ≥1 master** (giống algo 2; `UWB_ALGORITHMS=(2,5)`).

---

## 2. Vì sao tightly-coupled cần EKF

- Loosely-coupled (algo 2): tầng LS cho ra vị trí → measurement của bộ lọc là vị trí → H tuyến
  tính → **KF tuyến tính là đủ**.
- Tightly-coupled (algo 5): measurement là **range thô** `h(x)=‖p−aᵢ‖` (phi tuyến) → cần
  **Jacobian của range** → **EKF**.
- **Ưu điểm:** dùng đo thô (không mất thông tin qua bước LS); **vẫn cập nhật được khi <3 anchor**
  sau khi đã khởi tạo (mỗi range là một ràng buộc vô hướng độc lập); gate riêng từng range nên loại
  NLoS sạch hơn. **Nhược:** phi tuyến (nhạy điểm khởi tạo/dt), phức tạp hơn.

---

## 3. Kiến trúc (tightly-coupled)

```
range thô (cm) ─► cm→m + clamp [0.10, 30.0] m
              ─► EKF.step(dt):
                   • khởi tạo (frame đầu): LLS từ range → state [x, y, 0, 0]
                   • predict: F vận tốc-hằng (CV) + Q(dt)
                   • update: cho TỪNG range hợp lệ —
                       Hᵢ = [(px−ax)/h, (py−ay)/h, 0, 0],  ν = dᵢ − h,  S = HPHᵀ + R
                       nis = ν²/S ;  nis > GATE → bỏ ;  HUBER < nis ≤ GATE → phình R
                       cập nhật tuần tự (sequential scalar update)
              ─► (x, y) + (vx, vy)
```

**Các file:**
- `backend/algorithm_5.py` — `Algorithm5` (file chủ, bọc EKF cho MỘT tag).
- `backend/algorithms/trilateration_ekf/ekf.py` — `TrilaterationEKF` (toàn bộ logic).
- Khởi tạo LLS **dùng lại** `lls_initial_position` của algo 2 (`trilateration_LM/engine.py`).

---

## 4. Chi tiết EKF (tóm tắt — chi tiết ở READ_ME_tri_ekf.md)

- **State** `[x, y, vx, vy]` (vận tốc-hằng / white-noise-acceleration).
- **Predict:** `x=F·x`, `P=F·P·Fᵀ+Q(dt)`.
- **Update tuần tự** mỗi range: tính `Hᵢ`, innovation `ν`, `S`, `nis=ν²/S`; gate 3 mức:
  `nis>GATE` → **bỏ** (đếm rejected); `HUBER<nis≤GATE` → **phình R** (`R·nis/HUBER`); còn lại cập
  nhật bình thường. Cập nhật vô hướng nên không cần nghịch đảo ma trận.
- **Khởi tạo:** cần ≥`EKF_MIN_BEACONS_INIT` (=3) range; LLS seed → `[x,y,0,0]`; LLS suy biến →
  centroid anchor.

---

## 5. Tham số & cách hiệu chỉnh

Ở **đầu file** `ekf.py`:
`EKF_PROCESS_PSD=1.5`, `EKF_RANGE_STD_M=0.20` (R=σ²), `EKF_GATE_NIS=9.0`, `EKF_HUBER_NIS=4.0`,
`EKF_INIT_POS_VAR=4.0`, `EKF_INIT_VEL_VAR=1.0`, `EKF_MAX_DT_S=1.0`, `EKF_DEFAULT_DT_S=0.1`,
`EKF_MIN_BEACONS_INIT=3`. Ở `algorithm_5.py`: `RANGE_MIN_M=0.10`, `RANGE_MAX_M=30.0`.

> Hướng hiệu chỉnh khi có log UWB thật: `EKF_RANGE_STD_M` theo σ range LoS; `EKF_GATE_NIS`/
> `EKF_HUBER_NIS` theo bảng chi-square 1 bậc (mức loại/nghi ngờ); `EKF_PROCESS_PSD` theo dynamics.
> **`dt` quan trọng** (predict CV): runtime truyền thời gian thực giữa 2 nhịp range.

---

## 6. Kết quả kiểm chứng (synthetic 4 anchor)

| Kịch bản | Sai số vị trí |
|---|---|
| LoS sạch | ≈ 0.05 m |
| 1 anchor NLoS +1.5 m | ≈ 0.04 m (EKF **gate** loại range xấu; accepted/rejected = 3/1) |
| Mục tiêu di chuyển | ≈ 0.02 m |
| Chỉ còn 2 anchor (sau khởi tạo) | vẫn định vị được (lợi thế tightly-coupled) |

So với algo 2 (Huber-LM giảm trọng số → ≈0.35m ở kịch bản 1-anchor-NLoS): EKF gate hẳn range nên
sạch hơn. **Trần 4-anchor** vẫn áp dụng nếu ≥2 range lệch cùng lúc. **2D:** giả thiết đồng phẳng.

---

## 7. Nhúng vào trang realtime (đã hoàn thiện)

- **Pipeline dùng chung với algo 2:** coordinator `backend/algorithm_uwb.py` (`UWBManager`) +
  runtime `backend/mqtt_handle/trilateration_uwb/runtime.py` (`UWBRuntime`); bộ não chọn theo
  `run["algorithm"]` (=5 → `Algorithm5`).
- **Nhận/Gửi (MQTT):** giống hệt algo 2 — nhận `2/uwb_ranging/<master>/<slave>` + `uwb_id/<tag>`
  (IMU chỉ cho FOV+mô phỏng); gửi `user_pos/<tag>` + `fire_data` (giống algo 3).
- **Endpoint:** `POST /api/training-alg5/{id}/start` (body `UWBStartRequest`),
  `GET /api/training-alg5/{id}/state` (FE poll 700ms), `POST /api/training-alg5/{id}/admin`.
- **Trang:** `/training-live-algorithm5` (`training_live_algorithm5.{html,js}`) — bản sao y hệt
  trang algo 3; chỉ khác backend định vị. Panel chẩn đoán hiển thị "Beacons used" +
  **Ranges acc/rej**.
- **State** mỗi tag: như algo 2 nhưng thay `rms_error` bằng **`ranges_accepted`/`ranges_rejected`**;
  kèm tag ADMIN + `fires`/`root_fires`/`ended`/`outcome`.

---

## 8. Việc còn lại
- Hiệu chỉnh `EKF_RANGE_STD_M`, gates, PSD từ log UWB thật khi có.
- Bảo đảm có ≥3 range thật khi triển khai phần cứng (range về theo topic **slave**).
- (Tuỳ chọn) mô hình chuyển động tốt hơn CV; adaptive Q/R theo innovation.
