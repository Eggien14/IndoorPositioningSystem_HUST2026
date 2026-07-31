# Trilateration EKF — Thuật toán 5 (Tightly-coupled EKF)

Module này là **Thuật toán 5**: định vị tag trong 2D bằng cách **nạp thẳng range UWB thô vào
MỘT bộ EKF** — kiểu **tightly-coupled** (không có bước giải LS riêng).

> **Khác Thuật toán 2 (loosely-coupled):** algo 2 giải ra **vị trí** trước rồi mới lọc bằng
> Kalman tuyến tính. Algo 5 dùng **đo thô** trực tiếp (không mất thông tin qua bước LS) và
> **vẫn cập nhật được khi < 3 anchor** (sau khi đã khởi tạo) — đổi lại phức tạp hơn.
> Bản loosely-coupled: xem `../trilateration_LM/READ_ME_tri_lm.md`.

**Vì sao cần EKF (không phải KF tuyến tính):** ở đây phép đo là range phi tuyến
`h(x) = ‖p − aᵢ‖`, nên cần **Jacobian của range** ⇒ Extended Kalman Filter.

Chỉ dùng **UWB** (không IMU/PDR), KHÔNG có CIR → chống NLoS bằng **gate Mahalanobis/NIS + Huber**
trên từng range. Nguồn khoa học chung với algo 2: [`../trilateration_LM/reference_tri_lm.txt`](../trilateration_LM/reference_tri_lm.txt)
(mục 5 = vì sao tightly-coupled cần EKF). Tóm tắt cho AI agent: [`../CLAUDE_algor5.md`](../CLAUDE_algor5.md).

```text
range thô (cm) ─► cm→m + clamp [0.10, 30.0] m
              ─► EKF.step(dt):
                   • khởi tạo (frame đầu): LLS từ range → state [x, y, 0, 0]
                   • predict: F vận tốc-hằng (CV) + Q(dt)
                   • update: cho TỪNG range hợp lệ —
                        Hᵢ = [(px−ax)/h, (py−ay)/h, 0, 0]
                        NIS gate (bỏ nếu > GATE) ; Huber phình R nếu HUBER < NIS ≤ GATE
                        cập nhật tuần tự (sequential scalar update)
              ─► (x, y) + (vx, vy)
```

---

## Cấu Trúc

```text
backend/algorithms/trilateration_ekf/
  __init__.py        # export TrilaterationEKF
  ekf.py             # class TrilaterationEKF — toàn bộ logic tightly-coupled
  reference_tri_ekf.txt  # Đối chiếu literature + lý do dùng tightly-coupled EKF
  READ_ME_tri_ekf.md

backend/algorithm_5.py   # File CHỦ: class Algorithm5 — bọc TrilaterationEKF cho MỘT tag
```

> Bộ khởi tạo LLS **dùng lại** `lls_initial_position` của algo 2
> (`../trilateration_LM/engine.py`) — không lặp code. Tầng MQTT realtime (`UWBManager` +
> `UWBRuntime`) dùng `Algorithm5`, chọn theo `run["algorithm"] == 5`.

---

## 1. `ekf.py` — `TrilaterationEKF`

**Tham số ở đầu file:**
```python
EKF_PROCESS_PSD     = 1.5   # q: mật độ phổ gia tốc (m²/s³)
EKF_RANGE_STD_M     = 0.20  # σ đo range (m) → R = σ² mỗi range
EKF_GATE_NIS        = 9.0   # NIS > ngưỡng → LOẠI range (NLoS spike). χ²₁, α nhỏ
EKF_HUBER_NIS       = 4.0   # HUBER < NIS ≤ GATE → phình R = R·(NIS/HUBER) (robust)
EKF_INIT_POS_VAR    = 4.0   # P0 vị trí (m²)
EKF_INIT_VEL_VAR    = 1.0   # P0 vận tốc (m²/s²)
EKF_MAX_DT_S        = 1.0   # chặn dt (giây)
EKF_DEFAULT_DT_S    = 0.1   # dt mặc định khi không cấp
EKF_MIN_BEACONS_INIT = 3    # cần ≥3 anchor để KHỞI TẠO (sau đó cập nhật được với ít hơn)
```

State `x = [px, py, vx, vy]` (vận tốc-hằng). API chính:

- `step(beacon_positions, distances_m, dt) -> (x, y) | None` — một nhịp: khởi tạo nếu cần →
  predict → update. Trả `None` nếu chưa khởi tạo được.
- `predict(dt)` — `x = F·x`, `P = F·P·Fᵀ + Q(dt)` với `F` CV và `Q` white-noise-acceleration.
- `update_ranges(beacon_positions, distances_m) -> (accepted, rejected)` — cập nhật **tuần tự**
  từng range:
  - `Hᵢ = [(px−ax)/h, (py−ay)/h, 0, 0]`, `h = ‖p − aᵢ‖`, innovation `ν = dᵢ − h`.
  - `S = H·P·Hᵀ + R`, `nis = ν²/S`.
  - **Gate:** `nis > EKF_GATE_NIS` → **bỏ** range (đếm `rejected`).
  - **Robust Huber:** `EKF_HUBER_NIS < nis ≤ EKF_GATE_NIS` → **phình** `R ← R·(nis/EKF_HUBER_NIS)`.
  - Ngược lại cập nhật bình thường: `K = P·Hᵀ/S`, `x += K·ν`, `P = (I − K·H)·P`.
- `_init_from_ranges(...)` — khởi tạo bằng `lls_initial_position` (cần ≥ `EKF_MIN_BEACONS_INIT`);
  nếu LLS suy biến → dùng centroid các anchor.
- `.velocity`, `.last_accepted`, `.last_rejected`, `.reset()`.

> **Lợi thế tightly-coupled:** sau khi đã khởi tạo, EKF cập nhật được dù chỉ còn **2** (hoặc 1)
> range — vì mỗi range là một ràng buộc vô hướng riêng. Đồng thời range NLoS thường bị **gate**
> loại hẳn (sạch hơn so với chỉ giảm trọng số như Huber-LM của algo 2).

---

## 2. `backend/algorithm_5.py` — File chủ `Algorithm5`

**Tham số ở đầu file:**
```python
RANGE_MIN_M = 0.10          # loại range quá nhỏ
RANGE_MAX_M = 30.0          # loại range quá lớn
```
(Không có pre-filter Kalman từng anchor như algo 2 — `R` của EKF đã mô hình hoá nhiễu range trực tiếp.)

- `Algorithm5(beacon_positions: Dict[hex, (x, y)])` — hex chuẩn hoá `0x..` thường.
- `process_ranges(raw_distances_cm: Dict[hex, cm], dt: float|None) -> dict | None`:
  lọc dải range → `TrilaterationEKF.step(...)`. Trả
  `{x, y, velocity, num_beacons, ranges_accepted, ranges_rejected, filtered_distances_cm}`. `reset()`.

---

## 3. Lưu Ý & Giới Hạn

- **UWB-only**, không IMU/PDR; `uwb_id` (yaw/valve) chỉ phục vụ FOV + mô phỏng lửa ở tầng web.
- **Không CIR** → NLoS xử lý hoàn toàn bằng gate NIS + Huber.
- Khởi tạo cần ≥3 anchor; sau đó cập nhật được với ít hơn. Range NLoS dai dẳng thường bị gate
  loại (tốt), nhưng **trần 4-anchor** vẫn áp dụng nếu ≥2 range bị thiên cùng lúc.
- **2D**: anchor/tag ~ đồng phẳng (không z).
- `dt` quan trọng (predict CV): runtime truyền thời gian thực giữa 2 nhịp range.
- **Chưa có dataset UWB thật** → tham số theo literature; cần **hiệu chỉnh lại** `EKF_RANGE_STD_M`,
  `EKF_GATE_NIS`, `EKF_HUBER_NIS`, `EKF_PROCESS_PSD` khi có log thật.

## 4. Số Liệu Kiểm Chứng (synthetic 4 anchor)

| Kịch bản | Sai số vị trí |
|---|---|
| LoS sạch | ≈ **0.05 m** |
| 1 anchor NLoS +1.5 m | ≈ **0.04 m** (EKF **gate** loại range xấu; accepted/rejected = 3/1) |
| Mục tiêu di chuyển | ≈ **0.02 m** |
| Chỉ còn 2 anchor (sau khởi tạo) | vẫn định vị được (lợi thế tightly-coupled) |

(So sánh: Thuật toán 2 / Huber-LM giảm trọng số anchor NLoS → ≈ 0.35 m. Xem `../trilateration_LM/READ_ME_tri_lm.md`.)
