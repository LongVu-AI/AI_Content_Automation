# Hướng Dẫn Setup & Tích Hợp AI Content Automation (Cho Quân)

### Phần 1: TL;DR (Làm Nhanh Trong 3 Phút)
- **Bước 1**: Clone repo: `git clone https://github.com/LongVu-AI/AI_Content_Automation`
- **Bước 2**: Copy `.env.example` thành `.env`, điền Token và ID của Notion Database.
- **Bước 3**: Chạy `docker compose up -d --build` là xong, n8n ở cổng 5678, FastAPI ở 8000.

### Phần 2: Chuẩn bị (5 phút)
- **Yêu cầu hệ thống**: Máy cài sẵn **Docker Desktop** (Khuyên dùng), Git, và có tài khoản Notion.
- **Link tải Docker**: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **Cách kiểm tra Docker**: Mở terminal gõ lệnh sau, nếu hiện version là OK.
  ```bash
  docker --version
  ```

### Phần 3: Clone + Cấu hình (5 phút)
- **Clone code về máy**:
  ```bash
  git clone https://github.com/LongVu-AI/AI_Content_Automation
  cd AI_Content_Automation
  ```
- **Tạo Notion Integration**:
  1. Vào [notion.so/my-integrations](https://www.notion.so/my-integrations) tạo integration mới, copy thẻ **Internal Integration Secret**.
- **Tạo Database 20 cột**:
  1. Tạo 1 database mới trên Notion.
  2. Tạo đủ 20 cột (Tên cột và Type) y hệt trong file `docs/api-contract-step4.md`.
  3. **Đặc biệt quan trọng**: Bấm vào nút `...` góc phải trên cùng của Database -> **Connections** -> Tìm tên Integration vừa tạo và bấm **Share**.
- **Cấu hình `.env`**:
  Copy file `.env.example` thành `.env` (để file `.env` nằm ngang hàng file docker-compose). Điền 3 biến:
  ```env
  NOTION_TOKEN=secret_xxx
  NOTION_DATABASE_ID=xxx
  MASTER_DB_PROVIDER=notion
  ```

### Phần 4: Chạy hệ thống (2 phút)
- Khởi động toàn bộ cụm Server bằng lệnh:
  ```bash
  docker compose up -d --build
  ```
- Kiểm tra các container đã chạy chưa:
  ```bash
  docker ps
  ```
- Kiểm tra **FastAPI** (Nếu trả về `{"status":"ok"...}` là ngon):
  ```bash
  curl http://localhost:8000/health
  ```
- Kiểm tra **n8n**: Mở trình duyệt vào `http://localhost:5678`.

### Phần 5: Import workflow n8n
- Mở n8n (`http://localhost:5678`).
- Vào phần **Workflows** -> **Import from File**.
- Chọn file `n8n/Step4 - AI Agent Callback.json` trong source code.
- Góc trên cùng bên phải, bật toggle chuyển sang **Active**.

### Phần 6: Test webhook (10 phút)
Bạn có thể test xem webhook và kết nối Notion đã thông chưa:

- **Cách 1: Dùng Postman (Nhanh nhất)**
  1. Import 2 file trong thư mục `postman/` vào Postman.
  2. Đổi Environment góc trên bên phải thành **Local**.
  3. Chạy Request **AI Output Callback**.
- **Cách 2: Dùng curl**
  Copy và chạy thẳng ở Terminal/PowerShell:
  ```powershell
  curl.exe -X POST http://localhost:8000/api/v1/content/ai-output -H "Content-Type: application/json" -d '{\"request_id\":\"vid_test_001\",\"status\":\"success\",\"ai_result\":{\"hook_text\":\"test\"},\"metadata\":{},\"error\":null}'
  ```
- **Kết quả mong đợi**: Nhận về JSON dạng:
  ```json
  {"success":true,"data":{"request_id":"vid_test_001","notion_page_id":"xxx"},"error":null,"meta":{...}}
  ```
- **Cách verify**: Mở Notion Database lên xem có row nào mới tên `vid_test_001` không.

### Phần 7: Tích hợp với AI Agent của Quân
Khi hệ thống của mình chạy độc lập, AI Agent của bạn chỉ cần bắn POST request vào URL sau:
- **Webhook URL**: `http://localhost:5678/webhook/ai-agent-callback`
- **Method**: `POST`
- **Headers**: `Content-Type: application/json`
- **Body**: Push Data theo schema chuẩn (xem chi tiết ở `docs/api-contract-step4.md`).
- **Response**: Agent của bạn sẽ nhận lại JSON envelope chuẩn của FastAPI.

### Phần 8: Expose webhook ra public (Nếu cần)
Trường hợp AI Agent của bạn nằm trên một server khác (Cloud), bạn cần expose port của n8n ở local ra ngoài mạng:
- Dùng **Cloudflare Tunnel** (Tải về và gõ lệnh):
  ```bash
  cloudflared tunnel --url http://localhost:5678
  ```
- URL public nhận được sẽ có dạng `https://xxx.trycloudflare.com/webhook/ai-agent-callback`. Lấy link đó đút vào AI Agent của bạn.

### Phần 9: Troubleshooting
Bảng lỗi thường gặp:

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| Port 5678/8000 bị chiếm | App khác dùng port | Đổi port trong `docker-compose.yml` |
| `Missing NOTION_TOKEN` | `.env` sai vị trí | Đặt `.env` ngang hàng `docker-compose.yml` |
| Notion 401 | Token sai | Check lại token |
| Notion 404 | Chưa share DB với Integration | Vào Notion → Connections → Share |
| Webhook 404 | Workflow chưa Active | Vào n8n bật toggle Active |
| `ECONNREFUSED` | n8n dùng localhost | Đổi URL trong node n8n thành `http://python-service:8000` |

### Phần 10: Fallback nếu Quân KHÔNG cài được Docker
Nếu bí quá không cài được Docker Desktop, Quân có thể chạy manual (hơi cực):
- **Chạy FastAPI (Python)**:
  Mở terminal trong thư mục `python-service`:
  ```bash
  python -m venv .venv
  .venv\Scripts\activate   # Trên Windows (MacOS/Linux thì dùng source .venv/bin/activate)
  pip install -r requirements.txt
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  ```
- **Chạy n8n (NodeJS)**:
  Yêu cầu máy có NodeJS/npm:
  ```bash
  npm install n8n -g
  n8n start
  ```

### Phần 11: Liên hệ hỗ trợ
- Có lỗi gì trong lúc config cứ nhắn **Long** qua Telegram hoặc Slack nhé.
- Gửi kèm **ảnh chụp màn hình** lỗi hoặc copy paste log ra để mình fix cho lẹ!
