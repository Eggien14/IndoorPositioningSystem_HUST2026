# ESKF Module (Error-State Kalman Filter)

Module này là **Khối 3** của algorithm 3: **Transformer + PDR + ESKF**.

ESKF là **tầng fusion cuối cùng**, quyết định vị trí. Nó dung hòa:
- **PDR** (motion model) → `predict`: displacement `(Δx,Δy)` + độ bất định mỗi bước.
- **Transformer** (observation model) → `update`: tọa độ tuyệt đối `(x,y)`.

```text
RSSI ─> [Transformer] ─> Z_obs=(x,y), R≈(1.2m)² ──┐
                                                  ├─> [ESKF] ─> vị trí fused
IMU  ─> [PDR] ─> (Δx,Δy)+σ (StepEvent) ───────────┘  (predict)
```

Xem `reference_eskf.txt` để biết đối chiếu paper/dự án thực tế và công thức đầy đủ.

---

## Cấu Trúc

```text
backend/algorithms/eskf/
  config.py            # R (đo), P0, gating, fallback Q
  eskf_model.py        # ESKF2D + ESKFState
  reference_eskf.txt
  READ_ME_eskf.md
```

Điều phối với 2 khối kia: `backend/algorithm_3.py` (class `Algorithm3`).
Test tổng thể: `test/tran_pdr_eskf/test_tran_pdr_eskf.py`.

---

## Config ([config.py](config.py))

```python
R_MEAS_M = 1.2              # std đo của Transformer (mét) — LẤY TỪ sai số thật map_17
INITIAL_POSITION_STD_M = 3.0  # P0 = diag(std², std²)
MIN_PROCESS_STD_M = 0.05      # sàn cho Q mỗi bước
GATING_THRESHOLD = 9.21       # Mahalanobis chi² 2 DoF (~99%); None để tắt
FALLBACK_STEP_RATIO = 0.15    # nếu PDR không cấp sigma_step
FALLBACK_HEADING_DEG = 3.0
```

> **R = 1.2m, KHÔNG dùng 0.42m**: 0.42 là số rò rỉ của pipeline transformer cũ
> (random split). 1.2m là sai số THẬT (temporal split) trên map_17.

---

## Thuật Toán ([eskf_model.py](eskf_model.py)) — `ESKF2D`

State danh định `p=[x,y]`, error-state `δx`, hiệp phương sai `P` (2×2). H = I.

**predict(Δx, Δy, sigma_step, sigma_heading_deg, step_length):**
```text
p   <- p + [Δx, Δy]
Q   = diag(q², q²),  q = sqrt(sigma_step² + (L·rad(sigma_heading))²),  q >= MIN
P   <- P + Q            (F = I)
```

**update(z_x, z_y, r) -> accepted:bool:**
```text
δz  = z - p ;  S = P + R ;  R = diag(r², r²)
gating: nếu δzᵀ S⁻¹ δz > GATING_THRESHOLD -> BỎ QUA (nhảy NLOS), return False
K   = P S⁻¹ ;  δx̂ = K δz
p   <- p + δx̂   (INJECT) ;  P <- (I - K) P ;  reset δx̂ = 0
```

**get_state() -> ESKFState**: `x, y, pos_std, step_count, update_count, rejected_count`.

Demo: `.\venv\Scripts\python.exe backend\algorithms\eskf\eskf_model.py`

---

## Kết Quả Kiểm Chứng (end-to-end trên D8_1_1)

Chạy `Algorithm3` (Transformer map_17 + PDR + ESKF) trên test_case_D8_1_1:
```text
FUSED end = (1.96, 0.52)   (reference cell 2 = (1.5, 0.5))
PDR-only end = (1.56, 1.83) -> lệch y ~1.3m (drift)
=> ESKF KHỬ drift y của PDR bằng observation Transformer (y_fused ≈ 0.52 ≈ thật).
std = 0.20m | steps=50 | updates=267 chấp nhận | 2 observation NLOS bị gating loại.
```

---

## Giới Hạn & Mở Rộng

- **Position-only:** ESKF hiện chỉ ước lượng `(x,y)`. Nó kéo vị trí về observation
  nhưng KHÔNG sửa trực tiếp drift HƯỚNG của PDR. Mở rộng: thêm error-state hướng
  `δθ` (lúc đó mới cần Jacobian → ESKF đầy đủ).
- **Q/R thích nghi (nâng cấp):** tăng Q khi rẽ; R lớn hơn ở vùng cell rìa/NLOS.
- **Runtime MQTT** (`backend/mqtt_handle/transformer_pdr_eskf/`) **đã hoàn thiện** — ESKF chạy
  real-time trong `Algorithm3Manager` (sub `reality_id`, pub `user_pos`) + mô phỏng chữa cháy.
  Lưu ý: `offset_angle_bno` mặc định 0 ở runtime (giá trị −90 chỉ đúng cho bộ dữ liệu D8 cũ; phần
  cứng thật cần hiệu chỉnh lại).
