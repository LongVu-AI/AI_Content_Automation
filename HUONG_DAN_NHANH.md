# HƯỚNG DẪN SỬ DỤNG NHANH GÓI AUTOMATION (LONG V2)

> Thư mục: `integrations/long-v2`  
> Phục vụ: Chạy thử độc lập hệ thống Automation (FastAPI + n8n + Notion + TikTok) trên máy cục bộ hoặc Docker.

---

## 1. Cách 1: Chạy trực tiếp bằng Python (Nhanh nhất, Không cần Docker)

Nếu máy bạn chưa bật Docker Desktop, bạn có thể chạy thẳng bằng lệnh PowerShell:

```powershell
cd E:\Luu_Tru\Code_Data\AI-Tiktok\integrations\long-v2
.\run_local.ps1
```

- **API Swagger Docs**: Mở trình duyệt xem tại [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 2. Cách 2: Chạy kiểm thử tự động (1-Click Test)

Để kiểm tra xem hệ thống có hoạt động hoàn hảo không:

```powershell
cd E:\Luu_Tru\Code_Data\AI-Tiktok\integrations\long-v2
.\run_tests.ps1
```
Kết quả hiển thị: `10/10 TESTS PASSED (100%)`.

---

## 3. Cách 3: Chạy đầy đủ bằng Docker Compose (Cần mở Docker Desktop)

Khi bạn muốn chạy cả n8n và FastAPI trong container:
1. Mở ứng dụng **Docker Desktop** trên Windows.
2. Chạy lệnh:
```powershell
cd E:\Luu_Tru\Code_Data\AI-Tiktok\integrations\long-v2
.\run_docker.ps1
```
- **n8n Web UI**: [http://127.0.0.1:5678](http://127.0.0.1:5678)
- **FastAPI API**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 4. Các Workflows n8n có sẵn trong thư mục `n8n/`

1. `Content Studio - AI Agent Callback v2.json`: Nhận kịch bản 7 bước từ Web Studio v2 của Quân.
2. `Step4 - AI Agent Callback.json`: Nhận kịch bản v1.
3. `Step5 - Send Approval Request.json`: Tự động gửi tin nhắn Telegram kèm nút Duyệt/Sửa cho Bảo (mang mã phiên bản `revision`).
4. `Step5 - Handle Approval Callback.json`: Xử lý khi Bảo bấm nút trên Telegram.
5. `Step6 - Scheduling Cron.json`: Quét video đến giờ đăng.
6. `Step8 - TikTok Publish.json`: Tự động tải video lên TikTok và theo dõi trạng thái.
7. `Step9 - Retry Failed.json`: Thử lại các video bị lỗi mạng.
