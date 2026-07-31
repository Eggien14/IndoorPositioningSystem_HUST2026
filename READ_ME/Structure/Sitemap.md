# Sitemap — Các Trang Của Server

Tài liệu mô tả các trang (page route trả về HTML) hiện có, điều kiện truy cập và luồng
chuyển trang. Dành cho cả người dùng lẫn AI agent.

> Định vị/phân quyền là **phía client** (lưu trong localStorage); server không có
> middleware kiểm tra token. Vai trò: `1=admin`, `2=trainer`, `3=trainee`.

---

## 1. Danh sách trang

| URL | Template | JS | Chức năng ngắn gọn |
|---|---|---|---|
| `/` , `/login` | login.html | login.js | Đăng nhập vào hệ thống |
| `/home` | home.html | home.js | Trang trung tâm điều hướng |
| `/choose-map` , `/map-customization` | choose_map.html | choose_map.js | Chọn bản đồ để thao tác |
| `/create-map` | create_map.html | create_map.js | Tạo bản đồ mới |
| `/edit-map/{map_id}` | edit_map.html | edit_map.js | Chỉnh sửa ô lưới và beacon của bản đồ |
| `/collect-data/{map_id}` | collect_data.html | collect_data.js | Thu mẫu dữ liệu fingerprint theo ô |
| `/devices` | devices.html | devices.js | Quản lý thiết bị (tag/beacon) |
| `/training-sessions` | training_sessions.html | training_sessions.js | Danh sách & quản lý phiên huấn luyện |
| `/training-sessions/{session_id}/editor` | session_editor.html | session_editor.js | Soạn kịch bản (đám cháy) cho phiên |
| `/training-select` | training_select.html | training_select.js | Chọn map/thuật toán/thiết bị để bắt đầu; điều hướng sang trang real-time theo thuật toán |
| `/training-live` , `/training-live-test` | training_live.html | training_live.js | Màn hình huấn luyện real-time (chung) — dùng cho thuật toán 1/4 (stub) |
| `/training-live-algorithm2` | training_live_algorithm2.html | training_live_algorithm2.js | Real-time thuật toán 2 (UWB trilateration — Robust LM loosely-coupled) + mô phỏng cháy + ADMIN ảo. **Bản sao y hệt trang algo 3**, chỉ khác backend định vị |
| `/training-live-algorithm3` | training_live_algorithm3.html | training_live_algorithm3.js | Real-time thuật toán 3 (Transformer+PDR+ESKF) + mô phỏng cháy; có thiết bị ADMIN ảo điều khiển bằng bàn phím/chuột |
| `/training-live-algorithm5` | training_live_algorithm5.html | training_live_algorithm5.js | Real-time thuật toán 5 (UWB trilateration — tightly-coupled EKF) + mô phỏng cháy + ADMIN ảo. **Bản sao y hệt trang algo 3**, chỉ khác backend định vị |
| `/training-live-trilateration` | training_live_trilateration.html | training_live_trilateration.js | **LEGACY** — trang algo 2 cũ (UWB LM, runtime `trilateration_LM`). Vẫn chạy độc lập nhưng `training-select` không còn liên kết tới. Không dùng cho code mới |
| `/history` | history.html | history.js | Lịch sử các phiên huấn luyện đã hoàn thành |
| `/rickroll` | rickroll.html | — | Trang easter-egg |

Mọi trang đều nạp thêm `common.js` (theme, i18n EN/VI, AuthManager, modal, helper `api`,
toast, menu điều hướng theo vai trò).

---

## 2. Điều kiện truy cập
- `/` , `/login`: không cần đăng nhập.
- Các trang còn lại: cần đã đăng nhập (trạng thái lưu ở localStorage phía client).
- Tham số `{map_id}`, `{session_id}` phải tồn tại trong database.

---

## 3. Luồng chuyển trang

```
Đăng nhập (/)
   └─> /home  (trung tâm điều hướng)
        ├─ Nhánh bản đồ:    /choose-map ─> /create-map
        │                              └─> /edit-map/{id} ─> /collect-data/{id}
        ├─ Nhánh phiên:     /training-sessions ─> /training-sessions/{id}/editor
        ├─ Nhánh huấn luyện:/training-select ─> /training-live            (algo 1/4 — stub)
        │                                    ├─> /training-live-algorithm2 (algo 2 — UWB LM)
        │                                    ├─> /training-live-algorithm3 (algo 3 — Transformer+PDR+ESKF)
        │                                    └─> /training-live-algorithm5 (algo 5 — UWB EKF)
        ├─ Thiết bị:        /devices
        └─ Lịch sử:         /history
```

> 3 thuật toán đã có trang real-time hoàn chỉnh (định vị + mô phỏng kịch bản cháy + tính điểm +
> thiết bị ADMIN ảo): `/training-live-algorithm2` (UWB LM), `/training-live-algorithm3`
> (Transformer+PDR+ESKF), `/training-live-algorithm5` (UWB EKF). Hai trang algo 2 & 5 là **bản
> sao y hệt** trang algo 3, chỉ thay backend định vị. Algo 1/4 vẫn dùng trang chung
> `/training-live`. Trang `/training-live-trilateration` là **bản algo-2 cũ (legacy)**, còn chạy
> nhưng không còn được liên kết từ `/training-select`.
