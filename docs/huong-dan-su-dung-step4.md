# Hướng Dẫn Sử Dụng AI Content Automation (Step 4)

Hệ thống này cung cấp một Microservice (FastAPI) kết nối trực tiếp với **Notion Database** (chuẩn 20 cột mới nhất), cho phép quản lý nội dung và nhận kết quả trả về từ **AI Agent** qua n8n webhook một cách hoàn toàn tự động.

## 1. Yêu Cầu Cài Đặt (Prerequisites)
- Đã cài đặt **Docker** và **Docker Compose** (Docker Desktop trên Windows/Mac).
- Có tài khoản **Notion** và đã tạo một Integration (Lấy Internal Integration Secret Token).
- Đã share Notion Database (chứa 20 cột chuẩn) với Integration vừa tạo.

## 2. Cấu Hình Môi Trường (.env)
Trước khi chạy hệ thống, bạn cần cấu hình các thông tin xác thực. Mở thư mục gốc của project (ngang hàng với `docker-compose.yml`), tạo một file tên là `.env` (bạn có thể copy từ `.env.example` sang) với nội dung như sau:
```env
NOTION_TOKEN=secret_xxx_token_cua_ban_xxx
NOTION_DATABASE_ID=xxx_id_database_cua_ban_xxx
MASTER_DB_PROVIDER=notion
```
*(Lưu ý: Tuyệt đối không commit file `.env` chứa token thật lên GitHub hoặc gửi trực tiếp qua mạng hở)*

## 3. Khởi Chạy Hệ Thống
Mở terminal/PowerShell tại thư mục gốc của project và chạy lệnh:
```bash
docker compose down
docker compose up -d --build
```
Hệ thống sẽ build và khởi chạy 2 containers:
- **n8n**: chạy ở cổng `5678` (truy cập `http://localhost:5678`)
- **FastAPI**: chạy ở cổng `8000` (truy cập `http://localhost:8000/docs` để xem Swagger UI)

Bạn có thể xem log của API service bằng lệnh:
```bash
docker compose logs -f python-service
```

## 4. Các API Endpoints Chính

### 4.1. Health Check
Kiểm tra xem service có đang hoạt động tốt không.
- **GET** `http://localhost:8000/health`

### 4.2. Lấy Danh Sách Content
Lấy danh sách các trang nội dung từ Notion DB.
- **GET** `http://localhost:8000/api/v1/content?limit=5`

### 4.3. Intake Content Mới (Đẩy data đầu vào)
Tạo yêu cầu làm video mới.
- **POST** `http://localhost:8000/api/v1/content/intake`
- **Body JSON mẫu:**
  ```json
  {
    "request_id": "vid_20261001_001",
    "product_name": "Sản phẩm A",
    "product_link": "https://example.com"
  }
  ```

### 4.4. Nhận Kết Quả Từ AI Agent (Webhook n8n callback) - MỚI TRONG STEP 4
Endpoint này dùng để n8n (hoặc bất kỳ AI Agent nào) đẩy kết quả sinh content (Hook, Voice over, Caption, v.v.) ngược lại vào hệ thống để lưu lên Notion.
- **POST** `http://localhost:8000/api/v1/content/ai-output`
- **Body JSON mẫu:**
  ```json
  {
    "request_id": "vid_20261001_001",
    "status": "success",
    "ai_result": {
      "hook_text": "3 giây đầu thu hút...",
      "voice_over_text": "Kịch bản đọc Voice over...",
      "text_on_screen": "Chữ hiện trên màn hình",
      "image_prompt_en": "A highly detailed product...",
      "bgm_vibe": "Sôi động, trending",
      "post_caption": "Caption đăng TikTok...",
      "hashtags": ["#xuhuong", "#review"],
      "qc_score": 9.5,
      "qc_feedback": "Rất tốt, giữ nguyên",
      "retry_count": 0
    },
    "metadata": {
      "processing_time_seconds": 45,
      "model_used": "gemini-3.8-flash",
      "created_at": "2026-10-04T12:00:00+07:00"
    },
    "error": null
  }
  ```
**Logic hoạt động:** Hệ thống sẽ tự động tìm trong Notion DB xem `request_id` này đã có chưa. Nếu có rồi, nó sẽ update (ghi đè nội dung AI sinh ra). Nếu chưa có, nó sẽ tạo mới một trang. Thuộc tính `hashtags` sẽ tự động nối mảng thành chuỗi `#tag1 #tag2`. Thuộc tính `status` tự động chuyển thành `DRAFT` (nếu success) hoặc `FAILED` (nếu có lỗi).

## 5. Dùng Postman Để Test Nhanh
Để những người khác có thể sử dụng dễ dàng, trong folder `postman/` đã chuẩn bị sẵn file Collection và Environment:
1. Mở Postman, chọn **Import**.
2. Chọn 2 file: `local.postman_environment.json` và `AI_Content_Automation.postman_collection.json`.
3. Đảm bảo góc trên bên phải Postman đang chọn Environment là **Local**.
4. Chọn request **Content Intake** hoặc **AI Output** và nhấn Send!
