# Sổ tay Vận hành Hệ thống (Production Runbook)
## Dự án: AI Content Automation (FastAPI + n8n + Notion + TikTok + Telegram)

---

## 1. Sơ đồ Kiến trúc Tổng thể (Sau 9 Bước)

```text
[ Người dùng / Creator ]
         | (1) Đăng video / Duyệt nội dung
         v
+------------------+         +------------------+         +----------------------+
|  Telegram Group  |<------->|    n8n Engine    |<------->|  FastAPI Microservice|
|  (@mytdn_bot)    |         |  (Port: 5678)    |         |     (Port: 8000)     |
+------------------+         +--------+---------+         +-----------+----------+
                                      |                               |
                   (Orchestration & Cron Jobs)               (Business Logic & API)
                                      |                               |
                                      +---------------+---------------+
                                                      |
                             +------------------------+------------------------+
                             |                                                 |
                             v                                                 v
                  +---------------------+                           +--------------------+
                  |  Notion Master DB   |                           |     TikTok API     |
                  |  - Schema 22 cột    |                           |  - OAuth 2.0       |
                  |  - Tokens DB        |                           |  - Video Upload    |
                  +---------------------+                           +--------------------+
```

---

## 2. Danh sách Endpoints FastAPI

Tất cả endpoints trả về chuẩn JSON envelope: `{ "success": bool, "data": dict|null, "error": dict|null, "meta": dict }`.

| Method | Endpoint | Mô tả |
| :--- | :--- | :--- |
| `GET` | `/health` | Kiểm tra tính sẵn sàng của microservice |
| `POST` | `/api/v1/content/intake` | Tiếp nhận yêu cầu sinh kịch bản / video |
| `POST` | `/api/v1/content/ai-output` | Lưu kết quả sinh từ AI Agent vào Notion DB |
| `GET` | `/api/v1/content` | Lấy danh sách video (hỗ trợ phân trang) |
| `GET` | `/api/v1/content/pending-review` | Lấy danh sách video chờ duyệt |
| `GET` | `/api/v1/content/scheduled-due` | Lấy danh sách video APPROVED đến giờ đăng |
| `GET` | `/api/v1/content/failed` | Lấy danh sách video FAILED để retry (retry_count < 3) |
| `GET` | `/api/v1/content/{request_id}` | Lấy chi tiết thông tin video theo ID |
| `PATCH`| `/api/v1/content/{request_id}/status` | Cập nhật trạng thái video (APPROVED, PENDING_REVIEW, ...) |
| `POST` | `/api/v1/content/{request_id}/lock` | Khóa trạng thái video (Status Locking) chống trùng lặp |
| `POST` | `/api/v1/content/{request_id}/publish` | Đánh dấu video bắt đầu quy trình xuất bản |
| `GET` | `/api/v1/tiktok/auth` | Khởi tạo luồng xác thực OAuth 2.0 TikTok |
| `GET` | `/api/v1/tiktok/callback` | Tiếp nhận OAuth redirect callback và lưu token |
| `GET` | `/api/v1/tiktok/status` | Kiểm tra trạng thái kết nối tài khoản TikTok |
| `POST` | `/api/v1/tiktok/refresh` | Chủ động làm mới access token TikTok |
| `POST` | `/api/v1/tiktok/poc-upload` | POC khởi tạo upload video với TikTok |
| `POST` | `/api/v1/tiktok/publish-from-url` | Đăng video qua direct public URL |
| `POST` | `/api/v1/tiktok/publish-from-file`| Đăng video từ file local (chunked upload) |
| `POST` | `/api/v1/tiktok/check-status` | Kiểm tra trạng thái xuất bản TikTok và sync Notion |
| `POST` | `/api/v1/tiktok/webhook` | Tiếp nhận callback sự kiện publish từ TikTok |

---

## 3. Danh sách Workflows n8n

| Workflow | Tên file JSON | Trigger / Lịch trình | Nhiệm vụ chính |
| :--- | :--- | :--- | :--- |
| **Step 4** | `Step4 - AI Agent Callback.json` | Webhook | Tiếp nhận payload kịch bản từ AI Agent và đẩy sang FastAPI |
| **Step 5A**| `Step5 - Send Approval Request.json` | Schedule / Webhook | Gửi tin nhắn kèm nút Duyệt / Sửa sang nhóm Telegram |
| **Step 5B**| `Step5 - Handle Approval Callback.json`| Telegram Webhook | Tiếp nhận callback khi admin bấm nút trên Telegram |
| **Step 6** | `Step6 - Scheduling Cron.json` | Cron `*/5 * * * *` | Quét video APPROVED đến hạn, thực hiện Atomic Status Lock |
| **Step 8** | `Step8 - TikTok Publish.json` | Cron `*/10 * * * *`| Lấy video đến hạn, gửi lệnh publish, polling trạng thái TikTok |
| **Step 9** | `Step9 - Retry Failed.json` | Cron `*/15 * * * *`| Quét các video FAILED (retry_count < 3) để thử đăng lại |

---

## 4. Hướng dẫn Xử lý Sự cố (Incident Handling)

### 4.1. Vị trí file Log & Cách tra cứu
- **Đường dẫn trên Host**: `E:\Luu_Tru\Code_Data\AI_Content_Automation\logs\app.log`
- **Đường dẫn trong Container**: `/app/logs/app.log`
- Log được định dạng JSON chuẩn. Có thể lọc theo `request_id`, `level`, hoặc `logger`.
- Xem log thời gian thực:
  ```powershell
  docker logs -f ai-automation-python
  ```

### 4.2. Khởi động lại dịch vụ (Restart Service)
- Khởi động lại toàn bộ stack:
  ```powershell
  docker compose down
  docker compose up -d
  ```
- Chỉ khởi động lại service Python:
  ```powershell
  docker compose restart python-service
  ```

### 4.3. Cách xoay vòng (Rotate / Re-auth) Token TikTok
Nếu access_token và refresh_token đều hết hạn:
1. Mở trình duyệt truy cập: `http://localhost:8000/api/v1/tiktok/auth`
2. Đăng nhập và xác nhận ủy quyền tài khoản TikTok.
3. Kiểm tra lại trạng thái:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8000/api/v1/tiktok/status"
   ```

### 4.4. Cấu hình lại Telegram Webhook khi URL ngrok thay đổi
Khi khởi động lại ngrok, URL public thay đổi:
1. Cập nhật `TIKTOK_REDIRECT_URI` trong file `.env`.
2. Đăng ký lại Telegram webhook:
   ```bash
   https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=<NGROK_URL>/webhook/telegram-callback
   ```
3. Khởi động lại container để nhận biến môi trường mới:
   ```powershell
   docker compose up -d
   ```

---

## 5. Checklist Vận hành Định kỳ

### 5.1. Vận hành hàng ngày
- [ ] Kiểm tra dung lượng thư mục `logs/` (hệ thống tự rotate khi file > 10MB, lưu tối đa 5 file).
- [ ] Kiểm tra thông báo lỗi trên Telegram group xem có cảnh báo `[CRITICAL]` hoặc `[ERROR]` nào không.
- [ ] Kiểm tra số lượng video trạng thái `FAILED` qua endpoint `GET /api/v1/content/failed`.

### 5.2. Vận hành hàng tuần
- [ ] Kiểm tra hạn dùng của TikTok OAuth token (thông thường refresh token có hạn 365 ngày).
- [ ] Dọn dẹp các video mẫu tạm thời trong thư mục `test-videos/`.
- [ ] Kiểm tra số lượng execution trong n8n UI (`http://localhost:5678`) và xóa các execution log cũ nếu cần dọn dẹp dung lượng volume `n8n_data`.

---

## 6. Bảng Tra cứu Mã Lỗi & Cách Khắc phục

| Mã lỗi | Nguyên nhân | Hướng dẫn khắc phục |
| :--- | :--- | :--- |
| `MAX_RETRY_EXCEEDED` | Video đã retry quá 3 lần vẫn thất bại | Kiểm tra cột `last_error` trong Notion, sửa lỗi video hoặc liên kết rồi reset `retry_count` về 0 thủ công |
| `NOT_AUTHENTICATED` | Chưa có token TikTok trong hệ thống | Truy cập `/api/v1/tiktok/auth` để cấp quyền |
| `TOKEN_EXPIRED` | Access token hết hạn và refresh thất bại | Gọi `/api/v1/tiktok/refresh` hoặc thực hiện OAuth lại |
| `RATE_LIMIT_EXCEEDED` | Gọi TikTok API quá tần suất cho phép | Hệ thống sẽ tự động backoff và thử lại sau 2-8 giây |
| `CONTENT_NOT_FOUND` | Không tìm thấy `request_id` trong Notion | Kiểm tra lại tính chính xác của `request_id` |
| `NOTION_API_ERROR` | Notion API từ chối hoặc sai schema | Kiểm tra `NOTION_TOKEN`, quyền chia sẻ database và tên các thuộc tính |
| `INTERNAL_ERROR` | Lỗi ngoại lệ 500 phía server | Kiểm tra stack trace chi tiết trong `logs/app.log` |

