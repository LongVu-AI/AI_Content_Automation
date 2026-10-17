# API Contract (Buoc 8) - TikTok Video Upload & Publish Tracking

Tai lieu dac ta ky thuat cho tinh nang dang video len TikTok va theo doi trang thai publish tu dong ve Notion DB.

---

## 1. Tong quan co che Upload Video TikTok

TikTok Content Posting API (v2) ho tro 2 phuong thuc upload chinh:

### 1.1. PULL_FROM_URL
- **Co che**: He thong gui mot duong dan truc tiep toi video (public URL). May chu TikTok se chu dong tai video tu URL nay ve he thong TikTok.
- **Uu diem**: Khong ton tai nguyen may chu noi bo (RAM/Bandwidth) de truyen tai file video.
- **Yeu cau**: URL phai public, co the truy cap truc tiep (vi du: CDN, Google Cloud Storage bucket, AWS S3 public/presigned).

### 1.2. FILE_UPLOAD (Chunked Upload)
- **Co che**: He thong khoi tao yeu cau upload file tu may chu noi bo. TikTok tra ve `upload_url`. Sau do he thong chia video thanh tung chunk (5MB - 64MB) va thuc hien HTTP PUT voi header `Content-Range`.
- **Uu diem**: Ho tro video nam cuc bo tren may chu ma khong can upload len CDN cong khai truoc.
- **Bao mat**: Duong dan video duoc kiem tra thong qua danh sach whitelist thu muc (`/app/test-videos`).

---

## 2. Danh sach Endpoints

### 2.1. POST `/api/v1/tiktok/publish-from-url`
Khoi tao publish video len TikTok bang phuong thuc `PULL_FROM_URL`.

- **Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "request_id": "vid_20261016_001",
  "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
  "title": "Kham pha cong nghe AI moi nhat #AI #Tech",
  "privacy_level": "SELF_ONLY"
}
```
*Ghi chu:* Neu `video_url` bi bo trong, he thong se tu dong doc gia tri `video_url` da duoc luu trong Notion Database ung voi `request_id`.

- **Response Body**:
```json
{
  "success": true,
  "data": {
    "publish_id": "v_pub_file~v2.123456789012345678",
    "status": "PUBLISHING"
  },
  "error": null,
  "meta": {
    "request_id": "6d78fa1b-4f4c-4e8c-8fbd-19d4b6ecbb3a",
    "timestamp": "2026-10-16T14:30:00.000000+00:00"
  }
}
```

---

### 2.2. POST `/api/v1/tiktok/publish-from-file`
Upload va publish video truc tiep tu file tren may chu (chia chunks).

- **Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "request_id": "vid_20261016_002",
  "video_path": "/app/test-videos/demo.mp4",
  "title": "Review san pham thuc te",
  "privacy_level": "SELF_ONLY"
}
```

- **Response Body**:
```json
{
  "success": true,
  "data": {
    "publish_id": "v_pub_file~v2.987654321098765432",
    "status": "PUBLISHING"
  },
  "error": null,
  "meta": {
    "request_id": "a90184c2-0ec5-407b-89ff-968652077e38",
    "timestamp": "2026-10-16T14:31:00.000000+00:00"
  }
}
```

---

### 2.3. POST `/api/v1/tiktok/check-status`
Kiem tra trang thai publish tren TikTok va tu dong dong bo vao Notion DB.

- **Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "request_id": "vid_20261016_001"
}
```

- **Response Body**:
```json
{
  "success": true,
  "data": {
    "request_id": "vid_20261016_001",
    "old_status": "PUBLISHING",
    "new_status": "PUBLISHED",
    "tiktok_status": "PUBLISH_COMPLETE",
    "fail_reason": "",
    "description": "Video da duoc xu ly va publish thanh cong tren TikTok"
  },
  "error": null,
  "meta": {
    "request_id": "42ff3287-3c35-42ce-92c1-d249f3e46c7d",
    "timestamp": "2026-10-16T14:32:00.000000+00:00"
  }
}
```

---

### 2.4. POST `/api/v1/tiktok/webhook`
Endpoint tiep nhan webhook callback su kien publish tu TikTok Developer Portal.

- **Request Body**: JSON payload tu TikTok
- **Response Body**:
```json
{
  "status": "ok"
}
```

---

## 3. Bang anh xa Trang thai (TikTok Status -> Notion DB Status)

| TikTok API Status | Y nghia tu TikTok | Notion DB Status | Hanh dong bo sung |
| :--- | :--- | :--- | :--- |
| `PROCESSING_UPLOAD` | Video dang duoc upload/nhan du lieu | `PUBLISHING` | Cap nhat tiktok_publish_id vao Notion |
| `PROCESSING_DOWNLOAD` | TikTok dang download video tu public URL | `PUBLISHING` | Giu nguyen status PUBLISHING |
| `SEND_TO_USER_INBOX` | Video da gui ve Inbox user de xac nhan (Sandbox) | `PUBLISHING` | Cho user mo ung dung TikTok duyet |
| `PUBLISH_COMPLETE` | Video da publish thanh cong len profile | `PUBLISHED` | Ghi timestamp hien tai vao `published_at` |
| `FAILED` | Qua trinh publish bi that bai | `FAILED` | Ghi chi tiet loi vao `last_error` |

---

## 4. Chien luoc Polling trong n8n

Do TikTok API xu ly video bat dong bo (asynchronous transcoding & content moderation), qua trinh publish thuong mat tu 30 den 120 giay:
1. **Buoc 1**: Goi `POST /api/v1/tiktok/publish-from-url`. Nhan `publish_id`.
2. **Buoc 2**: Chuyen sang node `Wait 60s` de cho may chu TikTok download va transcode video.
3. **Buoc 3**: Goi `POST /api/v1/tiktok/check-status`.
4. **Buoc 4**:
   - Neu `new_status == "PUBLISHED"`, hoan thanh quy trinh cho item nay.
   - Neu chua hoan thanh (`PUBLISHING`), cho them `30s` va goi lai `POST /api/v1/tiktok/check-status` (toi da 5 lan thu lai).
   - Neu qua 5 lan thu lai, giu status `PUBLISHING` de cron dot sau tiep tuc kiem tra hoac nhan callback qua webhook.

---

## 5. Xu ly loi thuong gap & Troubleshooting

1. **Loi `401 Unauthorized / Token Expired`**:
   - `TikTokPublisher` co san co che phat hien token het han va tu dong goi `refresh_access_token` tu Notion Tokens DB. Nguoi dung khong can dang nhap lai thu cong tru khi refresh_token da het han (sau 365 ngay).
2. **Loi `400 Invalid Privacy Level` trong moi truong Sandbox**:
   - Trong che do TikTok Developer Sandbox, chi duoc phep chon `privacy_level: "SELF_ONLY"`. Khong chon `PUBLIC_TO_EVERYONE` vi tai khoan developer chua qua audit san pham.
3. **Loi `403 Whitelist Directory Error` (FILE_UPLOAD)**:
   - Duong dan file video phai nam trong thu muc duoc chi dinh: `/app/test-videos`.
4. **Loi `video_url inaccessible` (PULL_FROM_URL)**:
   - Dam bao may chu TikTok co the truy cap truc tiep vao video URL ma khong can qua session/cookies dang nhap.

