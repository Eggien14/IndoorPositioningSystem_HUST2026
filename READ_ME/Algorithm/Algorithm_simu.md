# Thuật Toán Mô Phỏng Huấn Luyện Chữa Cháy (Lan lửa · Dập lửa · Tính điểm)

Tài liệu dành cho **lập trình viên**: giải thích cơ chế mô phỏng kịch bản cháy chạy
real-time. Mô phỏng này **dùng chung cho cả 3 thuật toán có trang realtime: 2, 3 và 5** —
chỉ khác nguồn vị trí (algo 3 = RSSI/PDR; algo 2/5 = UWB ranging), phần lan/dập lửa + tính điểm
y hệt nhau. Phần định vị xem `READ_ME/Algorithm/Algorithm_2.md`, `Algorithm_3.md`, `Algorithm_5.md`;
hợp đồng truyền thông xem `READ_ME/Comunicate/MQTT.md`.

> **Mọi tham số tinh chỉnh đều nằm ở ĐẦU file tương ứng** trong `backend/simulation/`.
> Tài liệu tóm tắt cho AI agent: `backend/simulation/CLAUDE_simu.md`.

---

## 1. Tổng quan kiến trúc

Khi người dùng bắt đầu một phiên huấn luyện (session) bằng thuật toán 3, server tạo một
`SessionSimulation` chạy song song với việc định vị. Cứ ~0.1 giây (10 Hz), một vòng lặp
`asyncio` trong `backend/main.py` lại "bước" mô phỏng một nhịp:

```
Vị trí thiết bị (MQTT reality_id → ESKF)
        │  (ảnh chụp mỗi tick: x, y, yaw_map, valve.open, valve.mode)
        ▼
SessionSimulation.step(dt):
   spawn lửa → lan lửa → hao/nạp nước → dập lửa → tính điểm → kiểm tra kết thúc
        │
        ├─→ publish fire_data (mỗi khi bản đồ lửa đổi)
        ├─→ publish user_pos (kèm điểm; khi di chuyển hoặc khi điểm đổi)
        └─→ lưu session_history khi kết thúc tự nhiên
```

Các file:

| File | Vai trò |
|---|---|
| `backend/simulation/fire_spread.py` | `FireGrid` — bản đồ chỉ số lửa song song bản đồ chính: spawn + lan |
| `backend/simulation/extinguish.py` | Phát hiện cung phun trúng ô, giảm cường độ, hao nước |
| `backend/simulation/scoring.py` | Tham số + công thức tính điểm |
| `backend/simulation/simulator.py` | `SessionSimulation` — ghép 3 phần trên, chạy theo tick |

Chế độ **creative** (không chọn session) ⇒ không có mô phỏng, chỉ tracking.

---

## 2. Lan lửa (`fire_spread.py`)

Mỗi ô lửa lưu: cường độ `level (0–5)`, `fire_spread` (số ô lan mỗi chu kỳ), `fire_spread_time`
(chu kỳ lan, giây), thời điểm lan kế tiếp, cờ gốc/lan, và `spread_count` (số lần ô gốc đã lan).

- **Xuất hiện (spawn):** ngọn lửa gốc của session xuất hiện đúng `fire_time_seconds` (đếm từ
  lúc bấm Start) tại toạ độ của nó, với cường độ `fire_level`.
- **Lan:** cứ mỗi `fire_spread_time` giây, **mọi** ô đang cháy lan ra `fire_spread` ô kề (ngẫu
  nhiên trong 8 ô lân cận, trong biên bản đồ), **cộng `(cường_độ − 1)`** vào ô đích, chặn trần 5.
  - Ví dụ: ô mức 4 nhận lan từ nguồn mức 3 (cộng 2) → 5; ô mức 1 nhận cộng 3 → 4; ô mức 5 giữ 5.
  - Ô lan kế thừa đặc tính lan của nguồn; nếu nhiều nguồn dồn vào một ô: lấy `fire_spread_time`
    **nhỏ nhất** + `fire_spread` **lớn nhất** (lan nhanh & mạnh nhất).
  - **`spread_count` của ô gốc tăng MỖI chu kỳ lan**, kể cả khi cường độ mức 1 không lan ra ô
    nào (vì ô đó vẫn có thể bị nguồn khác lan vào để tăng cường độ; mục tiêu huấn luyện là phải
    dập GỐC càng sớm càng tốt — `spread_count` cao sẽ ăn mòn điểm thưởng gốc, xem §4).
- Lửa **được phép lan vào cả ô không đi được** (tường) — đúng quy ước "8 ô xung quanh".

---

## 3. Dập lửa & nước (`extinguish.py`)

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `VALVE_MIN_EFFECTIVE` | 10 | van ≤ 10% không dập được lửa |
| `SECONDS_PER_LEVEL_AT_MIN_VALVE` | 3.6 | van 10% → 3.6 giây/mức |
| `SECONDS_PER_LEVEL_AT_MAX_VALVE` | 0.5 | van 100% → 0.5 giây/mức (lửa mức 4 cần 2 giây) |
| `WATER_MAX` | 100 | dung tích bình **mặc định** (dự phòng); dung tích thật mỗi thiết bị lấy từ DB `device.water_capacity` |
| `WATER_DRAIN_PER_SEC_AT_MAX_VALVE` | 5.0 | van 100% → −5/giây (van x% → −x/100·5) |
| `SPRAY` | tỏa 60°/1.5m · tia 20°/2.5m | hình học cung phun (nguồn duy nhất; frontend tự lấy qua API) |

- **Cung phun:** hướng = `yaw_map` (góc nhìn người dùng, 0° = +Oy). `valve.mode ≤ 50` ⇒ phun
  **tỏa** (góc 60°, bán kính tối đa 1.5 m); `> 50` ⇒ phun **tia** (góc 20°, bán kính tối đa 2.5 m).
  Bán kính tỉ lệ với `valve.open` (0–100% ↔ 0 → bán kính tối đa).
- **Trúng lửa:** tâm ô lửa phải nằm trong cung phun thì mới dập được ô đó. Một thiết bị có thể
  dập nhiều ô cùng lúc.
- **Tốc độ:** nội suy tuyến tính theo `valve.open` (3.6 s/mức ở van 10 → 0.5 s/mức ở van 100). Nhiều
  thiết bị cùng phun một ô **không làm nhanh hơn** (dùng van lớn nhất), nhưng **điểm chia đều**.
- **Nước:** van mở > 0 thì hao nước (theo độ mở) bất kể có trúng lửa hay không. Hết nước ⇒ không
  dập được. **Đứng vào ô "điểm tập kết" ⇒ nạp đầy bình** (về đúng dung tích thiết bị, trừ khi đã
  bị truất quyền).
- **Dung tích nước mỗi thiết bị** lấy từ DB `device.water_capacity`: `-1` = **vô hạn** (không bao
  giờ cạn, luôn phun được), `>=0` = bình hữu hạn (mặc định 100). Thiết bị ADMIN ảo = vô hạn.

---

## 4. Tính điểm (`scoring.py`)

| Tham số | Mặc định |
|---|---|
| `INITIAL_SCORE` | 1000 |
| `PENALTY_PER_LEVEL_PER_SEC` | 100 |
| `DQ_FIRE_SECONDS` | 5.0 |
| `USE_SPEC_INSTANT_DQ` | False |
| `POINTS_PER_LEVEL` | 20 |
| `SPREAD_FIRE_COMPLETION` | 100 |
| `ROOT_SPREAD_GRACE` | 5 |
| `ROOT_SPREAD_BONUS` | 1000 |
| `ROOT_INTENSITY_BONUS` | 200 |
| `TIME_REMAINING_BONUS_PER_SEC` | 100 |

- Bắt đầu **1000 điểm**, không giới hạn trên, **chặn sàn 0** (không âm).
- **Đi vào ô lửa:** trừ `cường_độ × 100` mỗi giây.
- **Truất quyền** (khoá điểm 0 + nước 0 vĩnh viễn): ở trong lửa **LIÊN TỤC** quá
  `DQ_FIRE_SECONDS` giây (bộ đếm reset khi rời khỏi lửa). Đặt `USE_SPEC_INSTANT_DQ=True` để quay
  về quy tắc gốc (âm điểm là loại ngay).
- **Điểm dập lửa = 2 thành phần TÁCH BIỆT, CỘNG DỒN:**
  1. *Giảm cường độ*: mỗi mức giảm được = **+20** (cả lửa gốc và lửa lan), tính ngay.
  2. *Thưởng hoàn thành* (chỉ khi ô về 0):
     - lửa **lan** (hoặc lửa gốc đã lan quá 5 lần): **+100**;
     - lửa **gốc** (`spread_count ≤ 5`): `(5 − spread_count) × 1000 + cường_độ_gốc × 200`.
- **Dập chung:** điểm của ô chia đều cho các thiết bị đang phun trúng ô đó.
- **Kết thúc thành công:** cộng `thời_gian_còn_lại × 100` cho mọi thiết bị chưa bị truất quyền.
  **Hết giờ mà còn lửa ⇒ tất cả 0 điểm.**

> Thiết kế ưu tiên **dập nguồn (gốc) thật nhanh**: thưởng gốc rất lớn nhưng giảm dần theo số lần
> lan, còn lửa lan chỉ đáng ít điểm ⇒ chống "cày điểm" bằng cách thả cho lửa lan rồi dập con.

**Ví dụ:** dập lửa gốc mức 3 trước khi nó kịp lan → `3×20 + 5×1000 + 3×200 = 5660` điểm (chưa kể
1000 điểm khởi tạo + thưởng thời gian). Dập một ô lửa lan mức 2 → `2×20 + 100 = 140` điểm.

---

## 5. Điều phối & kết thúc (`simulator.py`)

Thứ tự mỗi tick: spawn → lan → hao/nạp nước → dựng danh sách thiết bị đang phun → dập lửa →
cộng điểm dập → phạt đứng-trong-lửa + kiểm tra truất quyền → kiểm tra kết thúc → dựng gói `fire_data`.

- **Kết thúc:**
  - Hết thời gian session mà **còn** lửa → thất bại, **mọi điểm về 0**.
  - Hết thời gian mà sạch lửa, hoặc mọi lửa gốc đã xuất hiện & bị dập sạch (kể cả lửa lan) →
    **thành công**, cộng thưởng thời gian.
- Khi kết thúc tự nhiên, server tự lưu `session_history` (điểm cuối + thời gian) cho từng thiết
  bị. **Nút Stop = dừng khẩn cấp, KHÔNG lưu lịch sử.**

---

## 6. Dữ liệu gửi về thiết bị (MQTT)

- **`fire_data`** (mỗi khi bản đồ lửa đổi): danh sách MỌI ô lửa (gốc + lan) còn cháy. Theo đúng
  quy tắc: tin chứa ô **vừa tắt** vẫn kèm ô đó với `level=0` và `fires_num` còn đếm nó; tin kế
  tiếp mới bỏ ô và giảm `fires_num`. Khi kết thúc, gửi tin chốt `fires_num=0`.
- **`user_pos`** (kèm `score`): gửi mỗi khi có vị trí mới (lúc thiết bị di chuyển) và định kỳ
  ~1 giây khi điểm thay đổi (để thiết bị luôn biết điểm hiện tại dù đứng yên).

Chi tiết schema: `READ_ME/Comunicate/MQTT.md`.

---

## 7. Tọa độ hiệu chỉnh (giữ thiết bị trong bản đồ)

Đôi khi đầu ra sau ESKF rơi ra ngoài biên bản đồ. Server tự "kéo" toạ độ về trong map trước khi
**hiển thị**, **gửi `user_pos`** và **đưa vào mô phỏng** (tính điểm / xác định ô lửa):
- `x < 0` → `0.1`; `x > X` (chiều ngang map) → `X − 0.1`; tương tự cho `y` với chiều dọc `Y`.
- Chỉ sửa trục bị lệch; cả hai cùng lệch thì sửa cả hai; còn nằm trong map thì giữ nguyên.

Trạng thái nội bộ của bộ lọc ESKF **không bị thay đổi** — đây chỉ là bước hiệu chỉnh ở khâu
hiển thị/giao tiếp/mô phỏng, nên thuật toán định vị vẫn nguyên vẹn.

## 8. Thiết bị ADMIN ảo

Một thiết bị "ảo" (tên **ADMIN**, hex `0xAD`) **không có trong database**, để người quản lý trực
tiếp tham gia bài tập từ màn hình server. Bật/tắt bằng ô **"Virtual ADMIN device"** trên thanh tác
vụ (chỉ chỉnh được trước khi Start). Khi bật, thẻ ADMIN xuất hiện trong bảng thông số thiết bị
(kèm ô chọn màu riêng).

- **Tham gia như một thiết bị thật**: vẫn tính điểm, dập lửa, bị phạt khi vào lửa — **chỉ khác**
  là vị trí/hướng/van do người điều khiển nhập trực tiếp (không qua MQTT). ADMIN dùng **bình nước
  vô hạn**. ADMIN **vẫn publish `user_pos/0xAD`** từ vòng lặp mô phỏng y như một thiết bị thật (mỗi
  thiết bị publish đúng hex của mình), nhưng **không lưu `session_history`** (vì không có `device_id`).
- Áp dụng cho cả 3 thuật toán: đẩy trạng thái ADMIN qua `POST /api/training-alg{2,3,5}/{id}/admin`.
- **Chế độ điều khiển**: bấm **CONTROL** trên thẻ ADMIN để vào, **Esc** để thoát:
  - `W/A/S/D`: di chuyển theo hệ toạ độ Descartes (W = +Oy/lên, S = −Oy, A = −Ox, D = +Ox), ~2.5 ô/giây.
  - **Chuột**: hướng nhìn (cũng là hướng phun) bám theo con trỏ trong "Bản đồ realtime".
  - **Lăn chuột**: tăng/giảm độ mở van (0–100).
  - **Chuột phải**: đổi chế độ phun (tỏa ↔ tia).
- Nút **Enable/Disable** trên thẻ ADMIN: tạm ẩn/hiện ADMIN trên bản đồ (khác ô tick trên thanh tác
  vụ — ô tick thêm/bỏ hẳn thẻ ADMIN và không đổi được khi đang chạy).
- Dùng được cả ở **creative mode** (chỉ di chuyển/phun minh hoạ, không lửa/điểm).

## 9. Tinh chỉnh

Toàn bộ tham số ở đầu các file `fire_spread.py` / `extinguish.py` / `scoring.py`. Khi đổi hình
học cung phun trong `extinguish.py` (`SPRAY`), **không cần** sửa frontend nữa: cả 3 trang realtime
(algo 2/3/5) tự lấy `SPRAY` qua `GET /api/sim/spray-config` lúc vào trang, nên sửa `SPRAY` là nón
vẽ trên bản đồ tự cập nhật theo. Tốc độ di chuyển ADMIN ở hằng `ADMIN_SPEED_CELLS_PER_SEC` trong
các file frontend `training_live_algorithm{2,3,5}.js`.
