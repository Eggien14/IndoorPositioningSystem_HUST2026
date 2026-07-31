# API Reference

Tất cả route HTTP của server (định nghĩa trong `backend/main.py`). Dành cho AI agent + dev.

**Quy ước:**
- Phân quyền: cột "Role" = `[1,2]` nghĩa là chỉ admin/trainer; truyền qua **query param**
  `?role_id=` (không có middleware token; tin tưởng dựa trên client localStorage).
- Vai trò: `1=admin`, `2=trainer`, `3=trainee`.
- Page routes (trả HTML) xem `READ_ME/Structure/Sitemap.md`.

---

## Auth
| Method | Path | Body / Params | Notes |
|---|---|---|---|
| POST | `/api/auth/login` | `{username, password}` | → `{username, role_id, role_name}` |

## Maps & Cells
| Method | Path | Body / Params | Role |
|---|---|---|---|
| GET | `/api/maps` | — | — |
| GET | `/api/maps/{map_id}` | — | — |
| POST | `/api/maps` | `MapCreate` (map_name, length_x, width_y, offset_angles) | — |
| PUT | `/api/maps/{map_id}/offset-angle` | `{offset_angles: float}` | — |
| DELETE | `/api/maps/{map_id}` | — | — |
| GET | `/api/maps/{map_id}/cells` | — | — |
| POST | `/api/maps/{map_id}/send-map-mqtt` | — | Publish passable cells → MQTT topic `map_data`; 503 if broker down |
| PUT | `/api/cells/{cell_id}` | `CellUpdate` (cell_index, is_passable) | — |
| PUT | `/api/cells/batch` | `{cells: [CellUpdate...]}` | — |
| GET | `/api/cells/{cell_id}/sample-count` | `?campaign_id=` | — |

## Beacons
| Method | Path | Body / Params | Role |
|---|---|---|---|
| GET | `/api/maps/{map_id}/beacons` | — | — |
| POST | `/api/maps/{map_id}/beacons` | `MapBeaconCreate` (hex_id, beacon_type, coord_x, coord_y) — max 1 UWB master | — |
| PUT | `/api/beacons/{beacon_id}` | `MapBeaconUpdate` (fields optional) | — |
| DELETE | `/api/beacons/{beacon_id}` | — | — |

## Algorithms (per map)
| Method | Path | Body / Params | Notes |
|---|---|---|---|
| GET | `/api/algorithm-names` | — | `{ "1":..,"2":..,"3":..,"4":..,"5":.. }` — nguồn tên thuật toán duy nhất (FE đọc để khỏi lệch). Có **5** thuật toán (xem cuối file) |
| GET | `/api/maps/{map_id}/algorithms` | — | Enabled algorithm IDs |
| PUT | `/api/maps/{map_id}/algorithms` | `{algorithms: [1..5]}` (full replace) | Validates beacons: fingerprint(1/3/4)≥3 wifi/ble; trilateration UWB (2 **và** 5)≥3 UWB beacon gồm ≥1 UWB master |

## Simulation (cấu hình dùng chung)
| Method | Path | Body / Params | Notes |
|---|---|---|---|
| GET | `/api/sim/spray-config` | — | Hình học nón phun nước, đọc thẳng từ `backend/simulation/extinguish.py` (`SPRAY`). Trả `{ spread: {half_angle_deg, max_radius_m}, jet: {half_angle_deg, max_radius_m} }`. **Nguồn duy nhất** cho cả backend (xét trúng lửa) lẫn frontend (vẽ nón) — sửa tham số trong `extinguish.py` là UI tự cập nhật |

## Campaigns & Fingerprints
| Method | Path | Body / Params | Notes |
|---|---|---|---|
| GET | `/api/maps/{map_id}/campaigns` | — | — |
| POST | `/api/campaigns` | `CampaignCreate` (map_id, sample_number, campaign_name) | — |
| GET | `/api/campaigns/{campaign_id}` | — | — |
| DELETE | `/api/campaigns/{campaign_id}` | — | — |
| GET | `/api/campaigns/{campaign_id}/statistics` | — | Per-cell sample counts |
| GET | `/api/campaigns/{campaign_id}/cells/{cell_id}/fingerprints` | — | — |
| DELETE | `/api/campaigns/{campaign_id}/cells/{cell_id}/fingerprints` | — | Reset cell data |
| POST | `/api/fingerprints` | `FingerprintCreate` (campaign_id, cell_id, wifi×4, ble×4, acc/gyro/mag×3, yaw/roll/pitch) | Manual insert |

## Data Collection (MQTT-driven)
| Method | Path | Body / Params | Notes |
|---|---|---|---|
| POST | `/api/data-collection/start` | `{campaign_id, cell_id, mqtt_topic}` | → `session_key = "{campaign_id}_{cell_id}"`; auto-stops at target sample count |
| POST | `/api/data-collection/stop` | `{session_key}` | — |
| GET | `/api/data-collection/status/{session_key}` | — | Poll progress |

## Devices
| Method | Path | Body / Params | Role |
|---|---|---|---|
| GET | `/api/devices` | — | Trả cả `water_capacity` mỗi thiết bị |
| POST | `/api/devices` | `DeviceCreate` (device_name, device_hex_id, **water_capacity** mặc định 100) ; `?role_id=` | [1,2] |
| PUT | `/api/devices/{device_id}` | `DeviceUpdate` (mọi field optional, gồm **water_capacity**) ; `?role_id=` | [1,2] |
| DELETE | `/api/devices/{device_id}` | `?role_id=` | [1,2] |

> `water_capacity`: sức chứa bình nước mỗi thiết bị — `-1` = vô hạn (không bao giờ cạn),
> `>=0` = bình hữu hạn (cạn khi phun, nạp lại ở điểm tập kết), mặc định `100`. Các trang
> real-time đọc giá trị này từ `GET /api/devices` để vừa hiển thị vừa nạp vào thuật toán mô phỏng.

## Sessions
| Method | Path | Body / Params | Role |
|---|---|---|---|
| GET | `/api/sessions` | — | — |
| GET | `/api/maps/{map_id}/sessions` | — | — |
| GET | `/api/sessions/{session_id}` | — | — |
| POST | `/api/sessions` | `SessionCreate` (session_name, map_id, duration_seconds) ; `?role_id=` | [1,2] |
| PUT | `/api/sessions/{session_id}` | `SessionUpdate` ; `?role_id=` | [1,2] |
| DELETE | `/api/sessions/{session_id}` | `?role_id=` | [1,2] |

## Session Fire Events
| Method | Path | Body / Params | Role |
|---|---|---|---|
| GET | `/api/sessions/{session_id}/fires` | — | — |
| POST | `/api/sessions/{session_id}/fires` | `SessionFireCreate` (time, level, spread, spread_time, coord_x, coord_y) ; `?role_id=` | [1,2] |
| POST | `/api/sessions/{session_id}/fires/by-cell` | `SessionFireClickCreate` (..., cell_id) ; `?role_id=` | [1,2] |
| DELETE | `/api/session-fires/{session_fire_id}` | `?role_id=` | [1,2] |

## Training & History
| Method | Path | Body / Params | Notes |
|---|---|---|---|
| POST | `/api/training/start` | `TrainingStartRequest` (username, role_id, map_id, session_id, device_ids, algorithm) | Prepare run → `training_run_id`; in-memory (lost on restart); trainee limited to 1 device |
| POST | `/api/training/{training_run_id}/start` | — | Begin run (generic). Với `algorithm==2` khởi động `trilateration_runtime` của **trang legacy** `/training-live-trilateration`. Trang mới algo 2/5/3 KHÔNG dùng endpoint này — chúng có endpoint riêng bên dưới |
| GET | `/api/training/{training_run_id}` | — | In-memory run state |
| GET | `/api/training-lm/{training_run_id}/state` | — | Real-time trilateration state (**chỉ cho trang algo-2 legacy**) |
| POST | `/api/training/finish` | `TrainingFinishRequest` (training_run_id, score) | Cleanup. Chỉ lưu `session_history` cho thuật toán **không mô phỏng** (1/4). Các thuật toán mô phỏng (3, 2, 5) do mô phỏng tự lưu khi kết thúc tự nhiên; Stop = không lưu |
| GET | `/api/history` | — | All completed session records |

## Algorithm 3 realtime (Transformer + PDR + ESKF)
| Method | Path | Body / Params | Notes |
|---|---|---|---|
| GET | `/api/training-alg3/maps/{map_id}/models` | — | Campaign của map + cờ `has_model` (có `transformer_model.pt` chưa) |
| POST | `/api/training-alg3/{training_run_id}/start` | `Algorithm3StartRequest` (campaign_id, start_x?, start_y?, offset_angle_bno?, assembly_x?, assembly_y?, admin_enabled?) | Bắt đầu runtime algo 3 + (nếu có session) mô phỏng cháy; `admin_enabled` bật thiết bị ADMIN ảo |
| POST | `/api/training-alg3/{training_run_id}/admin` | `Algorithm3AdminState` (x, y, yaw_map, valve_open, valve_mode, visible) | Đẩy trạng thái thiết bị ADMIN ảo (do người điều khiển trên màn hình server) — frontend gửi ~10 lần/giây |
| GET | `/api/training-alg3/{training_run_id}/state` | — | Trạng thái realtime algo 3: tags (vị trí/điểm/nước/..., kèm tag ADMIN `is_admin`), `fires`, `root_fires`, `ended`, `outcome` |

## Algorithm 2 & 5 realtime (UWB trilateration — dùng chung pipeline)
> Algo 2 (Robust LM, loosely-coupled) và algo 5 (EKF, tightly-coupled) **dùng chung một runtime
> UWB** (`uwb_runtime` + `uwb_manager`); chỉ khác "bộ não" định vị mỗi tag. Hai bộ endpoint giống
> hệt nhau, chỉ khác tiền tố `training-alg2` / `training-alg5`. State có dạng giống algo 3.

| Method | Path | Body / Params | Notes |
|---|---|---|---|
| POST | `/api/training-alg2/{training_run_id}/start` | `UWBStartRequest` (start_x?, start_y?, assembly_x?, assembly_y?, admin_enabled?) | Bắt đầu runtime UWB (bộ não LM) + (nếu có session) mô phỏng cháy |
| POST | `/api/training-alg2/{training_run_id}/admin` | `Algorithm3AdminState` | Đẩy trạng thái ADMIN ảo (giống algo 3) |
| GET | `/api/training-alg2/{training_run_id}/state` | — | State algo 2: mỗi tag có `position_x/y`, `cell_index`, `yaw_raw/map`, `valve_open/mode`, `spray_mode`, `num_beacons`, **`rms_error`**, `score`, `water_remaining`/`water_capacity`, `fires_extinguished`, `disqualified`; kèm tag ADMIN + `fires`/`root_fires`/`ended`/`outcome` |
| POST | `/api/training-alg5/{training_run_id}/start` | `UWBStartRequest` (giống algo 2) | Bắt đầu runtime UWB (bộ não EKF) + mô phỏng cháy |
| POST | `/api/training-alg5/{training_run_id}/admin` | `Algorithm3AdminState` | Đẩy trạng thái ADMIN ảo |
| GET | `/api/training-alg5/{training_run_id}/state` | — | State algo 5: giống algo 2 nhưng thay `rms_error` bằng **`ranges_accepted`/`ranges_rejected`** |

## Health
| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | `{status, timestamp, mqtt_connected}` |

---

## Phụ lục — 5 thuật toán định vị (`ALGORITHM_NAMES`)
| ID | Tên | Trạng thái real-time |
|----|------|--------|
| 1 | RSSI Fingerprints - CNN + PDR | Stub — dùng trang chung `/training-live` |
| 2 | Trilateration: Robust LM (loosely-coupled) | ✅ Đầy đủ — pipeline UWB chung + mô phỏng cháy |
| 3 | RSSI Fingerprints - Transformer + PDR + ESKF | ✅ Đầy đủ — runtime + mô phỏng cháy |
| 4 | RSSI Fingerprints - Multi modal cross attention | Stub |
| 5 | Trilateration: Tightly-coupled EKF | ✅ Đầy đủ — pipeline UWB chung + mô phỏng cháy |

`UWB_ALGORITHMS = (2, 5)` trong `main.py` gom 2 thuật toán dùng UWB ranging.

> Chi tiết định vị: `backend/algorithms/CLAUDE_algor2.md` (LM), `CLAUDE_algor3.md`
> (Transformer+PDR+ESKF), `CLAUDE_algor5.md` (EKF) cho AI agent; bản cho dev xem
> `READ_ME/Algorithm/Algorithm_2.md`, `Algorithm_3.md`, `Algorithm_5.md`. Mô phỏng lan/dập
> lửa + tính điểm: `READ_ME/Algorithm/Algorithm_simu.md`.
