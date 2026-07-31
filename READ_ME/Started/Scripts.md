# Hướng Dẫn Script Khởi Động / Dừng Server

Thư mục `scripts/` chứa 2 script PowerShell vận hành server:

- `scripts/start_server.ps1` — khởi động server.
- `scripts/stop_server.ps1` — dừng server.

> Chạy trong **PowerShell**, tại **thư mục gốc dự án**. Trước đó cần đã dựng môi
> trường theo `READ_ME/Started/Env.md` (đã có `venv/`).

---

## 1. `start_server.ps1` — Khởi động

### Tham số
| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `-Port <int>` | `8000` | Cổng chạy server |
| `-NoReload` | (tắt) | Tắt auto-reload (chạy ổn định / benchmark) |

### Script làm gì
1. Kiểm tra `venv/` tồn tại; nếu không có thì báo lỗi và dừng (yêu cầu xem `Env.md`).
2. **Tự kích hoạt venv** (`venv\Scripts\Activate.ps1`).
3. Kiểm tra cổng `-Port` có đang bị chiếm không; nếu có thì báo lỗi và yêu cầu chạy
   `stop_server.ps1` trước.
4. Chạy uvicorn từ thư mục gốc dự án:
   - Mặc định (có auto-reload): `python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port <Port>`
   - Khi `-NoReload`: `python -m uvicorn backend.main:app --host 127.0.0.1 --port <Port>`

### Cách dùng
```powershell
# Khởi động (auto-reload, cổng 8000)
.\scripts\start_server.ps1

# Không auto-reload (ổn định)
.\scripts\start_server.ps1 -NoReload

# Đổi cổng
.\scripts\start_server.ps1 -Port 8010
```
Server chạy tại `http://127.0.0.1:<Port>` (mặc định `http://127.0.0.1:8000`).
Nhấn `Ctrl+C` trong terminal để dừng.

> Lưu ý: script hard-code host `127.0.0.1`; biến `SERVER_HOST`/`SERVER_PORT` trong
> `.env` không được script sử dụng.

---

## 2. `stop_server.ps1` — Dừng

### Tham số
| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `-Port <int>` | `8000` | Cổng của server cần dừng |

### Script làm gì
1. Tìm các tiến trình đang **lắng nghe trên cổng** `-Port`.
2. Tìm thêm các tiến trình `python.exe`/`pythonw.exe` có dòng lệnh chứa
   `uvicorn ... backend.main:app` (bắt cả tiến trình reload phụ).
3. Tìm toàn bộ **tiến trình con** (descendants) của các tiến trình trên.
4. `Stop-Process -Force` tất cả (trừ chính tiến trình PowerShell đang chạy script).
5. Chờ 400ms rồi kiểm tra lại cổng; nếu vẫn bị chiếm thì báo cần chạy lại / dừng thủ công.

### Cách dùng
```powershell
# Dừng server cổng 8000
.\scripts\stop_server.ps1

# Dừng server ở cổng khác
.\scripts\stop_server.ps1 -Port 8010
```

---

## 3. Lệnh hữu ích kèm theo

```powershell
# Kiểm tra server có đang chạy trên cổng 8000 không
Get-NetTCPConnection -State Listen -LocalPort 8000
```

## 4. Quy trình vận hành đề xuất
1. `.\scripts\start_server.ps1` để chạy.
2. Khi cần khởi động lại sau khi sửa code (nếu chạy `-NoReload`): `stop_server.ps1`
   rồi `start_server.ps1`. Nếu chạy chế độ auto-reload (mặc định), uvicorn tự nạp lại.
3. Trước khi mở server thứ hai trên cùng cổng, luôn `stop_server.ps1` trước để tránh
   xung đột cổng.
