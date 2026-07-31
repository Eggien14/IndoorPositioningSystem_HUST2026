# Cấu Trúc File Của Server / Project File Structure

Tài liệu này liệt kê **toàn bộ** file/thư mục đang chạy của server và tóm tắt ngắn gọn nhiệm vụ
từng file. Dành cho cả dev mới lẫn AI agent.

> **Phạm vi:** bỏ qua 3 thư mục `test/` (test offline replay), `venv/` (môi trường ảo) và
> `Source/` (tài liệu/ server cũ — chỉ tham khảo, không bao giờ import). Mọi file còn lại đều
> được liệt kê bên dưới.

---

## 1. Sơ đồ tổng thể (overview)

```
Create_map_Collect_data/
├── backend/                    # FastAPI backend (toàn bộ logic server)
│   ├── main.py                 # App + tất cả route (API + page) + vòng lặp mô phỏng
│   ├── crud.py / models.py / database.py / init_db.py / mqtt_client.py
│   ├── algorithm_2.py / algorithm_3.py / algorithm_5.py / algorithm_uwb.py   # "bộ não" + coordinator định vị
│   ├── algorithms/             # Logic toán học từng thuật toán + tài liệu (READ_ME/reference)
│   ├── mqtt_handle/            # Các handler MQTT theo nhiệm vụ (thu data, định vị, publish)
│   └── simulation/             # Mô phỏng chữa cháy (lan lửa / dập lửa / tính điểm)
├── frontend/                   # Giao diện (Jinja2 + vanilla JS, không framework)
│   ├── templates/  static/js/  static/css/  img/
├── db/                         # Schema MySQL + migration
├── scripts/                    # Script PowerShell bật/tắt server
├── READ_ME/                    # Tài liệu cho developer (file bạn đang đọc nằm ở đây)
├── CLAUDE.md                   # Tài liệu tổng cho AI agent (coordinator)
├── data_extract.py             # Tiện ích trích fingerprint_data ra CSV
├── requirements.txt / .env / .gitignore
└── (test/, venv/, Source/      # bỏ qua — xem phạm vi ở trên)
```

---

## 2. `backend/` — lõi server

### 2.1 File gốc của backend
| File | Nhiệm vụ |
|---|---|
| `backend/__init__.py` | Đánh dấu package Python |
| `backend/main.py` | Ứng dụng FastAPI: định nghĩa **tất cả** route (page HTML + API), mount static/img, vòng lặp mô phỏng asyncio (`_algorithm3_sim_loop`, `_uwb_sim_loop`), `ALGORITHM_NAMES`, `UWB_ALGORITHMS=(2,5)` |
| `backend/crud.py` | Toàn bộ truy vấn MySQL (mysql-connector-python) |
| `backend/models.py` | Pydantic model cho request/response của tất cả API |
| `backend/database.py` | Connection pool MySQL (`pool_size=5`); print ASCII-only |
| `backend/init_db.py` | Chạy `db/init.sql` bằng Python (khởi tạo DB) |
| `backend/mqtt_client.py` | Singleton `mqtt_client` (lớp truyền tải MQTT thuần: subscribe/unsubscribe/publish/dispatch); đọc `MQTT_BROKER/PORT/KEEPALIVE` từ `.env` |

### 2.2 "Bộ não" định vị + coordinator (đặt thẳng trong `backend/`)
| File | Nhiệm vụ |
|---|---|
| `backend/algorithm_2.py` | `Algorithm2` — bộ não định vị mỗi tag cho thuật toán 2 (UWB trilateration, loosely-coupled: distance KF → LLS → robust LM → CV Kalman) |
| `backend/algorithm_5.py` | `Algorithm5` — bộ não định vị mỗi tag cho thuật toán 5 (UWB trilateration, tightly-coupled EKF) |
| `backend/algorithm_uwb.py` | `UWBManager` — coordinator chạy thật + mô phỏng + ADMIN ảo cho **cả algo 2 & 5** (chọn bộ não theo `run["algorithm"]`); bản sao cấu trúc của `Algorithm3Manager` |
| `backend/algorithm_3.py` | `Algorithm3` (fusion mỗi tag: Transformer+PDR+ESKF) + `Algorithm3Manager` (coordinator runtime + mô phỏng cho thuật toán 3) |

### 2.3 `backend/mqtt_handle/` — handler MQTT theo nhiệm vụ
| File | Nhiệm vụ |
|---|---|
| `mqtt_handle/CLAUDE_MQTT.md` | ⭐ Tài liệu lớp MQTT cho AI agent |
| `mqtt_handle/fingerprints_collectdata/__init__.py` | Export `fingerprint_collector` |
| `mqtt_handle/fingerprints_collectdata/collector.py` | `FingerprintCollector` singleton — thu mẫu fingerprint qua MQTT, lưu DB, tự dừng khi đủ số mẫu |
| `mqtt_handle/server_2_device/__init__.py` | Export `publish_user_pos`, `publish_fire_data` |
| `mqtt_handle/server_2_device/publisher.py` | Publish chiều Server→Device: `user_pos/<tag>` (mỗi lần giải vị trí) và `fire_data` (mỗi tick mô phỏng) |
| `mqtt_handle/transformer_pdr_eskf/__init__.py` | Export `algorithm3_runtime`, `model_exists` |
| `mqtt_handle/transformer_pdr_eskf/runtime.py` | `Algorithm3Runtime` singleton — sub `reality_id/<tag>`, nạp `Algorithm3Manager`, pub `user_pos` (thuật toán 3 real-time) |
| `mqtt_handle/trilateration_uwb/__init__.py` | Export `uwb_runtime` |
| `mqtt_handle/trilateration_uwb/runtime.py` | `UWBRuntime` singleton — sub `2/uwb_ranging/<m>/<s>` + `uwb_id/<tag>`, nạp `UWBManager`, pub `user_pos` (**thuật toán 2 & 5** real-time) |
| `mqtt_handle/trilateration_LM/__init__.py` | Export `trilateration_runtime` |
| `mqtt_handle/trilateration_LM/runtime.py` | `TrilaterationRuntime` — runtime của **trang algo-2 cũ (legacy)** `/training-live-trilateration`; vẫn chạy độc lập, không dùng cho code mới |

### 2.4 `backend/simulation/` — mô phỏng chữa cháy (Phase B)
| File | Nhiệm vụ |
|---|---|
| `simulation/__init__.py` | Export các lớp mô phỏng |
| `simulation/CLAUDE_simu.md` | ⭐ Tài liệu mô phỏng cho AI agent (đọc trước khi sửa lửa/điểm) |
| `simulation/fire_spread.py` | Mô hình lan lửa theo lưới ô (`FireGrid`) |
| `simulation/extinguish.py` | Cơ chế dập lửa + hình học nón phun `SPRAY` (spread/jet) — **nguồn duy nhất** cho góc/bán kính nón |
| `simulation/scoring.py` | Quy tắc tính điểm |
| `simulation/simulator.py` | `SessionSimulation` + `DeviceSim` (nước, phun, ghi điểm) — dùng chung cho algo 2/3/5 |

### 2.5 `backend/algorithms/` — toán học + tài liệu từng thuật toán
| File | Nhiệm vụ |
|---|---|
| `algorithms/CLAUDE_algor2.md` | ⭐ Tóm tắt thuật toán 2 (UWB LM) cho AI agent |
| `algorithms/CLAUDE_algor3.md` | ⭐ Tóm tắt thuật toán 3 (Transformer+PDR+ESKF) cho AI agent |
| `algorithms/CLAUDE_algor5.md` | ⭐ Tóm tắt thuật toán 5 (UWB EKF) cho AI agent |

**`algorithms/eskf/`** — Block 3 của thuật toán 3 (ESKF 2D):
| File | Nhiệm vụ |
|---|---|
| `eskf/__init__.py` | Export `ESKF2D` |
| `eskf/config.py` | Tham số ESKF (R đo, ngưỡng Mahalanobis, ...) |
| `eskf/eskf_model.py` | Lớp `ESKF2D` (predict bằng PDR, update bằng quan sát tuyệt đối) |
| `eskf/READ_ME_eskf.md` | Tài liệu dev cho khối ESKF |
| `eskf/reference_eskf.txt` | Tài liệu tham khảo + kiến trúc + kết quả ESKF |

**`algorithms/pdr/`** — Block 2 của thuật toán 3 (đếm bước, dead-reckoning):
| File | Nhiệm vụ |
|---|---|
| `pdr/__init__.py` | Export `PDRModel`, `StepEvent` |
| `pdr/config.py` | Tham số PDR (hệ số Weinberg, ngưỡng bước, ...) |
| `pdr/pdr_model.py` | `PDRModel` — phát hiện bước + ước lượng độ dời (Δx, Δy)+σ |
| `pdr/READ_ME_pdr.md` | Tài liệu dev cho khối PDR |
| `pdr/reference_pdr.txt` | Tài liệu tham khảo + kiến trúc + kết quả PDR |

**`algorithms/transformer/`** — Block 1 của thuật toán 3 (RSSI→tọa độ tuyệt đối):
| File | Nhiệm vụ |
|---|---|
| `transformer/__init__.py` | Export tiện ích model |
| `transformer/config.py` | Cấu hình trung tâm (MAP_ID, dải RSSI hợp lệ, kích thước model, tham số train) |
| `transformer/READ_ME_transformer.md` | Tài liệu dev khối Transformer (gồm cả pipeline huấn luyện) |
| `transformer/reference_transformer.txt` | Tài liệu tham khảo + kiến trúc + kết quả Transformer |
| `transformer/training/__init__.py` | Package huấn luyện |
| `transformer/training/preprocess.py` | Tiền xử lý dữ liệu fingerprint (lọc dải RSSI, scale) |
| `transformer/training/dataset.py` | Lớp Dataset PyTorch |
| `transformer/training/model_def.py` | Định nghĩa kiến trúc Transformer |
| `transformer/training/train.py` | Vòng huấn luyện (chạy độc lập) |
| `transformer/training/evaluate.py` | Đánh giá model (sai số mét) |
| `transformer/training/visualize.py` | Vẽ biểu đồ loss / quỹ đạo |
| `transformer/model/map_<id>/campaign_<id>/` | Artifact đã huấn luyện: `transformer_model.pt`, `scaler.joblib`, log train, biểu đồ (`.png`), CSV metric/predict (hiện có `map_15/campaign_14` và `map_17/campaign_18`) |

**`algorithms/trilateration_ekf/`** — thuật toán 5 (tightly-coupled EKF):
| File | Nhiệm vụ |
|---|---|
| `trilateration_ekf/__init__.py` | Export `TrilaterationEKF` |
| `trilateration_ekf/ekf.py` | `TrilaterationEKF` — predict CV + cập nhật Jacobian theo từng range + cổng NIS/Huber |
| `trilateration_ekf/READ_ME_tri_ekf.md` | Tài liệu dev cho thuật toán 5 |
| `trilateration_ekf/reference_tri_ekf.txt` | Tài liệu tham khảo + kiến trúc + kết quả thuật toán 5 |

**`algorithms/trilateration_LM/`** — thuật toán 2 (loosely-coupled robust LM):
| File | Nhiệm vụ |
|---|---|
| `trilateration_LM/__init__.py` | Export engine định vị |
| `trilateration_LM/engine.py` | `solve_trilateration_robust` — LLS seed + adaptive-λ LM + IRLS-Huber + WLS, trả covariance `P` (và `solve_trilateration_lm` cũ chỉ cho trang legacy) |
| `trilateration_LM/distance_kalman.py` | Kalman lọc khoảng cách từng anchor |
| `trilateration_LM/position_kf.py` | Kalman vận tốc không đổi (CV) làm mượt vị trí |
| `trilateration_LM/positioning.py` | Module định vị **legacy** (trang algo-2 cũ) |
| `trilateration_LM/user_state.py` | Trạng thái người dùng **legacy** |
| `trilateration_LM/READ_ME_tri_lm.md` | Tài liệu dev cho thuật toán 2 |
| `trilateration_LM/reference_tri_lm.txt` | Tài liệu tham khảo + kiến trúc + kết quả thuật toán 2 |

**`algorithms/fingerprints_CNN/`** — thuật toán 1 (chỉ có tài liệu, chưa triển khai):
| File | Nhiệm vụ |
|---|---|
| `fingerprints_CNN/READ_ME_cnn.md` | Tài liệu CNN (mô tả thuật toán 1 dựa trên server cũ) |
| `fingerprints_CNN/reference_cnn.txt` | Tài liệu tham khảo CNN |

---

## 3. `frontend/` — giao diện

### 3.1 `frontend/templates/` — trang HTML (Jinja2)
| File | Trang |
|---|---|
| `login.html` | Đăng nhập (`/`, `/login`) |
| `home.html` | Trung tâm điều hướng (`/home`) |
| `choose_map.html` | Chọn bản đồ (`/choose-map`, `/map-customization`) |
| `create_map.html` | Tạo bản đồ (`/create-map`) |
| `edit_map.html` | Sửa ô lưới/beacon (`/edit-map/{id}`) |
| `collect_data.html` | Thu mẫu fingerprint (`/collect-data/{id}`) |
| `devices.html` | Quản lý thiết bị (`/devices`) — có ô nhập `water_capacity` |
| `training_sessions.html` | Danh sách phiên (`/training-sessions`) |
| `session_editor.html` | Soạn kịch bản cháy (`/training-sessions/{id}/editor`) |
| `training_select.html` | Chọn map/thuật toán/thiết bị (`/training-select`) |
| `training_live.html` | Real-time chung — algo 1/4 (`/training-live`, `/training-live-test`) |
| `training_live_algorithm2.html` | Real-time thuật toán 2 (UWB LM) — bản sao trang algo 3 |
| `training_live_algorithm3.html` | Real-time thuật toán 3 (Transformer+PDR+ESKF) |
| `training_live_algorithm5.html` | Real-time thuật toán 5 (UWB EKF) — bản sao trang algo 3 |
| `training_live_trilateration.html` | Trang algo-2 **legacy** (`/training-live-trilateration`) |
| `history.html` | Lịch sử huấn luyện (`/history`) |
| `rickroll.html` | Easter-egg (`/rickroll`) |

### 3.2 `frontend/static/js/` — JS (mỗi trang một file + chung)
| File | Nhiệm vụ |
|---|---|
| `common.js` | Nạp trên mọi trang: ThemeManager, i18n EN/VI, AuthManager, ModalManager, helper `api`, toast, menu theo vai trò, `imgFallback`, `fetchSprayConfig` |
| `login.js` `home.js` `choose_map.js` `create_map.js` `edit_map.js` `collect_data.js` `devices.js` `training_select.js` `training_sessions.js` `session_editor.js` `history.js` | Logic tương ứng từng trang cùng tên |
| `training_live.js` | Trang real-time chung (algo 1/4) |
| `training_live_algorithm2.js` | Trang real-time algo 2 (UWB LM) |
| `training_live_algorithm3.js` | Trang real-time algo 3 (Transformer+PDR+ESKF) |
| `training_live_algorithm5.js` | Trang real-time algo 5 (UWB EKF) |
| `training_live_trilateration.js` | Trang algo-2 legacy |

### 3.3 Tài nguyên tĩnh khác
| Đường dẫn | Nhiệm vụ |
|---|---|
| `frontend/static/css/style.css` | Stylesheet duy nhất |
| `frontend/img/device/` | Ảnh thiết bị: `<device_id>.png`/`.jpg` (ưu tiên png), `lililaho.png` (fallback) |
| `frontend/img/map/` | Ảnh bản đồ: `<map_id>.png`/`.jpg`, `lililaho.png` (fallback), `README.txt` |
| `frontend/img/test_img/` | Ảnh icon dùng trong UI real-time (`fire.jpg`, `valve.png`, `mode.png`, `chart.png`) |

> Mount: `frontend/static/` → `/static`, `frontend/img/` → `/img` (trong `main.py`).

---

## 4. `db/` — cơ sở dữ liệu
| File | Nhiệm vụ |
|---|---|
| `db/init.sql` | Schema MySQL đầy đủ + 3 tài khoản mặc định. **Chỉ chạy khi dựng DB lần đầu**. Đã gồm sẵn `device.water_capacity`, ràng buộc `algorithm IN (1,2,3,4,5)`, cột `fire_spread`/`fire_spread_time` (kèm block migration nội bộ) |
| `db/device_water_add.sql` | Migration cho DB cũ: thêm cột `water_capacity` (prepared statement, chạy `Execute all`, an toàn khi chạy lại) |

---

## 5. `scripts/` — vận hành server
| File | Nhiệm vụ |
|---|---|
| `scripts/start_server.ps1` | Khởi động server (tự kích hoạt venv; `-Port`, `-NoReload`) |
| `scripts/stop_server.ps1` | Dừng server theo cổng + tiến trình uvicorn con |

---

## 6. `READ_ME/` — tài liệu cho developer
| File | Nhiệm vụ |
|---|---|
| `READ_ME/READ_ME_main.md` | ⭐ File điều phối tổng cho dev (đọc đầu tiên) — bản "CLAUDE.md cho người" |
| `READ_ME/Structure/API.md` | Mô tả toàn bộ API HTTP |
| `READ_ME/Structure/File_structure.md` | File bạn đang đọc — cấu trúc thư mục |
| `READ_ME/Structure/Sitemap.md` | Sơ đồ các trang + luồng chuyển trang |
| `READ_ME/Started/Env.md` | Dựng môi trường (venv, thư viện, `.env`, khởi tạo DB) |
| `READ_ME/Started/Scripts.md` | Hướng dẫn 2 script bật/tắt server |
| `READ_ME/Started/Docker.md` | (Trống — chưa dùng Docker) |
| `READ_ME/MySQL_db/Mysql_db.md` | Mô tả database (bảng, quan hệ, quy tắc) |
| `READ_ME/Comunicate/MQTT.md` | Hợp đồng truyền thông MQTT (topic, cấu trúc tin nhắn) |
| `READ_ME/Algorithm/Algorithm_1.md` | Tài liệu tổng thuật toán 1 (CNN+PDR+KF, theo server cũ) |
| `READ_ME/Algorithm/Algorithm_2.md` | Tài liệu tổng thuật toán 2 (UWB LM) |
| `READ_ME/Algorithm/Algorithm_3.md` | Tài liệu tổng thuật toán 3 (Transformer+PDR+ESKF) |
| `READ_ME/Algorithm/Algorithm_5.md` | Tài liệu tổng thuật toán 5 (UWB EKF) |
| `READ_ME/Algorithm/Algorithm_simu.md` | Tài liệu mô phỏng chữa cháy cho dev |

---

## 7. File ở thư mục gốc
| File | Nhiệm vụ |
|---|---|
| `CLAUDE.md` | ⭐ Tài liệu tổng cho AI agent (coordinator nối các file `CLAUDE_*.md`) |
| `data_extract.py` | Tiện ích CLI trích `fingerprint_data` của (map, campaign) ra CSV |
| `requirements.txt` | Thư viện Python (fastapi, uvicorn, mysql-connector, torch CPU, ...) |
| `.env` | Cấu hình DB + MQTT + server |
| `.gitignore` | Loại trừ venv/, cache, ... khỏi git |
| `.claude/settings.local.json` | Cấu hình cục bộ của công cụ Claude Code (không liên quan runtime server) |

---

## 8. Ghi chú nhanh
- **Điểm vào hiểu server:** dev đọc `READ_ME/READ_ME_main.md`; AI agent đọc `CLAUDE.md`.
- **Hai nhóm tài liệu tách biệt:** `CLAUDE*.md` (cho AI) và các `.md` trong `READ_ME/` +
  `READ_ME_*.md`/`reference_*.txt` (cho dev). Hai nhóm hạn chế trích dẫn lẫn nhau.
- **Trạng thái stub/placeholder:** thuật toán 1 (`algorithms/fingerprints_CNN/` — chỉ tài liệu)
  và thuật toán 4 (chưa có code); `READ_ME/Started/Docker.md` còn trống.
- **Legacy còn tồn tại nhưng không dùng cho code mới:** trang `/training-live-trilateration`
  và module `mqtt_handle/trilateration_LM/` + `algorithms/trilateration_LM/positioning.py`,
  `user_state.py`.
- **`Source/` chỉ để tham khảo** — code chạy thật nằm trong `backend/`, không bao giờ import từ `Source/`.
