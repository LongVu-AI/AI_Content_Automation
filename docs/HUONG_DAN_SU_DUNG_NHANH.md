# 🚀 Hướng Dẫn Sử Dụng Nhanh Hệ Thống AI Content Automation

Tài liệu hướng dẫn tinh gọn dành cho bộ phận **Content** và **AI Agent Developer**.

---

## 📱 Phần 1: Dành Cho Bảo (Content - Không Cần Cài Đặt)

> **Mục tiêu**: Nhập thông tin sản phẩm và duyệt video đã tạo trực tiếp trên điện thoại/máy tính qua Notion & Telegram.

### 📝 Hướng Dẫn Nhập Liệu Và Duyệt Video

* **Bước 1: Nhập sản phẩm mới**
  * Mở link database: [Notion Master Database](https://www.notion.so/3ebbd9bc891f80d1ac8dd0258c4473ed) 🔗
  * Bấm **+ New** để thêm dòng mới và điền 4 thông tin cơ bản:
    * `Tên sản phẩm` (Ví dụ: Tai nghe chống ồn Bluetooth Pro)
    * `Giá` (Ví dụ: 599.000 VNĐ)
    * `Link` (Đường dẫn sản phẩm Shopee/TikTok Shop)
    * `Đối tượng` (Ví dụ: Sinh viên, nhân viên văn phòng)

* **Bước 2: Chờ hệ thống AI tạo nội dung**
  * Hệ thống tự động chạy ngầm để viết kịch bản, chấm điểm chất lượng (QC) và render video.
  * Bảo chỉ cần chờ thông báo gửi về Telegram (thường mất khoảng 1 - 3 phút).

* **Bước 3: Xem và Duyệt video trên Telegram**
  * Mở Telegram và vào group **"AI Content Approval"** 💬
  * Xem video và nội dung đính kèm trong tin nhắn thông báo.
  * Bấm chọn 1 trong 2 nút bấm tương tác:
    * ✅ **[DUYỆT]** (APPROVED): Video đạt yêu cầu, tự động chuyển vào hàng đợi đăng lên TikTok theo lịch.
    * ⚠️ **[CẦN SỬA]** (NEEDS_REVISION): Kịch bản hoặc video chưa ưng ý, hệ thống sẽ đánh dấu để điều chỉnh lại.

* **Bước 4: Kiểm tra trạng thái trên Notion**
  * Quay lại bảng [Notion Master Database](https://www.notion.so/3ebbd9bc891f80d1ac8dd0258c4473ed), xem cột `status` đã đổi thành:
    * `APPROVED` (nếu bấm Duyệt) 
    * `NEEDS_REVISION` (nếu bấm Cần sửa)

---

## 💻 Phần 2: Dành Cho Anh Quân (AI Agent - Test Webhook)

> **Mục tiêu**: Chạy hệ thống local chỉ với 1-click để test gửi payload webhook từ AI Agent sang n8n và FastAPI.

### ⚡ Các Bước Chạy Môi Trường Local & Test Webhook

* **Bước 1: Chuẩn bị môi trường Docker**
  * Cài đặt [Docker Desktop](https://www.docker.com/products/docker-desktop/) (nếu máy chưa có).
  * Bật ứng dụng Docker Desktop lên và chờ biểu tượng góc dưới chuyển sang màu xanh (Docker is running).

* **Bước 2: Khởi động hệ thống (1-Click)**
  * Vào thư mục gốc dự án `AI_Content_Automation`.
  * Click đúp chuột vào file: `1_START_SYSTEM.bat` 🚀
  * File sẽ tự động kiểm tra Docker, cấu hình và khởi chạy cả 2 container:
    * **FastAPI Backend**: `http://localhost:8000/docs`
    * **n8n Workflow**: `http://localhost:5678`

* **Bước 3: Cấu hình Token (Chỉ làm lần đầu)**
  * Nếu là lần đầu chạy, file `.env` sẽ tự động được tạo từ `.env.example`.
  * Mở file `.env` bằng VS Code hoặc Notepad, điền thông tin:
    ```env
    NOTION_TOKEN=ntn_your_notion_token
    NOTION_DATABASE_ID=your_database_id
    MASTER_DB_PROVIDER=notion
    ```
  * Lưu file `.env` lại và click đúp chạy lại `1_START_SYSTEM.bat`.

* **Bước 4: Kích hoạt Workflow trên n8n**
  * Mở trình duyệt truy cập: `http://localhost:5678`
  * Vào menu **Workflows** ➡️ bấm nút **Import from File**.
  * Chọn file: `n8n/Step4 - AI Agent Callback.json`.
  * Gạt nút công tắc góc trên bên phải sang **Active** (màu xanh).

* **Bước 5: Cấu hình AI Agent gửi Webhook**
  * Trong code AI Agent của Quân, cấu hình gửi `POST` request đến webhook:
    ```http
    POST http://localhost:5678/webhook/ai-agent-callback
    Content-Type: application/json
    ```
  * Cấu trúc JSON payload mẫu (tham khảo chi tiết tại `docs/api-contract-step4.md`):
    ```json
    {
      "request_id": "vid_test_quan_001",
      "ai_result": {
        "hook_text": "3 cách tối ưu năng suất làm việc cho lập trình viên",
        "voice_over_text": "Nếu bạn đang bị ngợp vì deadline...",
        "text_on_screen": "Mẹo Dev 2026",
        "image_prompt_en": "A modern workspace with minimalist desk setup",
        "bgm_vibe": "lo-fi energetic",
        "post_caption": "Bỏ túi ngay 3 bí quyết này nhé! #dev #tips",
        "hashtags": "#dev,#coding,#productivity",
        "qc_score": 8.5,
        "qc_feedback": "Nội dung rõ ràng, hook tốt"
      }
    }
    ```

* **Bước 6: Tắt hệ thống khi test xong**
  * Khi hoàn tất buổi test, click đúp chuột vào file: `2_STOP_SYSTEM.bat` 🛑
  * Toàn bộ container sẽ được hạ xuống gọn gàng, giải phóng RAM cho máy.

---

## 🛠️ Tiện Ích Bổ Sung: Mở Tunnel Public (Khi Cần Test TikTok/Telegram Webhook)

* Nếu cần test webhook từ bên ngoài internet (TikTok Callback hoặc Telegram):
  * Click đúp chuột vào file: `3_START_TUNNEL.bat` 🌐
  * Copy đường dẫn HTTPS được cấp (ví dụ `https://xxxx.ngrok-free.dev`) dán vào cấu hình `TIKTOK_REDIRECT_URI` hoặc Telegram Webhook.
  * Giữ cửa sổ `3_START_TUNNEL.bat` luôn mở trong suốt quá trình test.

