# API Contract (Buoc 7) - TikTok OAuth 2.0 & Connection POC

Tai lieu dac ta ky thuat cho luong xac thuc OAuth 2.0 voi TikTok va cac API kiem tra ket noi, refresh token va POC upload video.

---

## 1. Tong quan luong xac thuc OAuth 2.0 (Step-by-Step)

Luong xac thuc theo tieu chuan Authorization Code Grant cua TikTok Open API v2:

```
[Nguoi dung (Trinh duyet)]
       |
       | 1. Truy cap GET /api/v1/tiktok/auth
       v
[FastAPI Microservice]
       |
       | 2. Sinh state (CSRF token), chuyen huong (307) sang:
       |    https://www.tiktok.com/v2/auth/authorize/?client_key=...&redirect_uri=...&scope=...&state=...
       v
[TikTok Login & Consent Screen]
       |
       | 3. Nguoi dung dang nhap TikTok va bam dong y cap quyen
       | 4. TikTok chuyen huong ve redirect_uri kem theo `code` va `state`
       v
[FastAPI Callback: GET /api/v1/tiktok/callback?code=...&state=...]
       |
       | 5. Kiem tra tinh hop le cua state
       | 6. POST https://open.tiktokapis.com/v2/oauth/token/ (doi code lay access_token & refresh_token)
       | 7. Luu tru token vao Notion Tokens Database (NOTION_TOKENS_DB_ID)
       | 8. Goi TikTok GET /v2/user/info/ de lay open_id va display_name
       v
[Trinh duyet hien thi thong bao xac thuc thanh cong]
```

---

## 2. Danh sach Endpoints

### 2.1. GET `/api/v1/tiktok/auth`
Khoi tao phien dang nhap TikTok.
- **Mo ta**: Sinh chuoi ngau nhien `state` luu vao bo nho tam thoi, sau do tra ve HTTP Redirect (302/307) den TikTok OAuth dialog.
- **Scope yeu cau**: `user.info.basic,video.upload,video.publish`

### 2.2. GET `/api/v1/tiktok/callback`
Endpoint tiep nhan Redirect tu TikTok sau khi nguoi dung cap quyen.
- **Query Params**:
  - `code` (string): Ma authorization code tu TikTok.
  - `state` (string): Ma chong gia mao CSRF.
- **Xu ly**:
  - Verify `state` voi du lieu da luu trong he thong.
  - Goi TikTok API doi `code` lay `access_token`, `refresh_token`, `expires_in`, `refresh_expires_in`.
  - Luu vao Notion Database `NOTION_TOKENS_DB_ID`.
- **Response**: HTML trang web thong bao thanh cong kem theo `display_name` va `open_id`.

### 2.3. GET `/api/v1/tiktok/status`
Kiem tra trang thai ket noi TikTok hien tai.
- **Response mau khi da ket noi:**
```json
{
  "success": true,
  "data": {
    "connected": true,
    "open_id": "_000abc123xyz...",
    "expires_at": "2026-10-17T11:00:00+00:00",
    "display_name": "My Channel Name"
  },
  "error": null,
  "meta": {
    "request_id": "uuid-here",
    "timestamp": "ISO8601"
  }
}
```
- **Response mau khi chua ket noi:**
```json
{
  "success": true,
  "data": {
    "connected": false
  },
  "error": null,
  "meta": {
    "request_id": "uuid-here",
    "timestamp": "ISO8601"
  }
}
```

### 2.4. POST `/api/v1/tiktok/refresh`
Chu dong lam moi access token bang refresh token.
- **Request Body**: Khong yeu cau (he thong tu lay refresh token moi nhat tu Notion DB).
- **Response**:
```json
{
  "success": true,
  "data": {
    "open_id": "_000abc123xyz...",
    "expires_in": 86400,
    "token_type": "Bearer"
  },
  "error": null,
  "meta": {
    "request_id": "uuid-here",
    "timestamp": "ISO8601"
  }
}
```

### 2.5. POST `/api/v1/tiktok/poc-upload`
POC kiem tra kha nang khoi tao upload video qua TikTok Content Posting API.
- **Request Body**:
```json
{
  "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"
}
```
- **Response**: Tra ve truc tiep phan hoi tu TikTok Content Posting API chua `publish_id`.
*(Luu y: Endpoint nay chi khoi tao o che do SELF_ONLY va khong dang cong khai de phuc vu kiem thu ket noi).*

---

## 3. Huong dan lay Access Token lan dau

1. Dam bao container `ai-automation-python` dang chay o port `8000`.
2. Mo trinh duyet (Chrome/Edge/Firefox) tren may tinh.
3. Nhap dia chi:
   `http://localhost:8000/api/v1/tiktok/auth`
4. Trinh duyet se tu dong chuyen huong den trang dang nhap va xac nhan cap quyen cua TikTok.
5. Dang nhap tai khoan TikTok can dang video va bam **Authorize** (Uy quyen).
6. Sau khi xac thuc, TikTok se chuyen huong ve `TIKTOK_REDIRECT_URI` va hien thi man hinh thong bao `Xac thuc TikTok thanh cong`.
7. Kiem tra lai tren terminal:
   `curl.exe http://localhost:8000/api/v1/tiktok/status`
   Ket qua se bao `connected: true`.

---

## 4. Co che tu dong Refresh Token
- TikTok Access Token co thoi han mac dinh la **24 gio** (86400 giay).
- Refresh Token co thoi han la **365 ngay** (31536000 giay).
- Trong endpoint `GET /api/v1/tiktok/status`:
  - He thong se goi `validate_token` kiem tra access token voi TikTok API.
  - Neu token da het han, he thong se tu dong su dung `refresh_token` de xin cap token moi, cap nhat vao Notion Tokens Database ma khong can nguoi dung phai dang nhap lai thu cong.

---

## 5. Xu ly su co (Troubleshooting)

| Hien tuong | Nguyen nhan | Huong xu ly |
|---|---|---|
| `Redirect URI mismatch` | URL callback khong khop voi cau hinh tren TikTok Developer Portal | Kiem tra bien `TIKTOK_REDIRECT_URI` trong file `.env` phai trung khop tung ky tu voi muc Redirect Domain/URI tren portal TikTok |
| `Invalid client_key` | `TIKTOK_CLIENT_KEY` chua duoc dien dung | Kiem tra lai Client Key trong Developer Portal ung dung TikTok cua ban |
| `Scope not allowed` | App chua duoc duyet cac quyen video | Tren TikTok Developer Portal, dam bao ung dung da dang ky cac scopes: `user.info.basic`, `video.upload`, `video.publish` |
| `token_expired_and_refresh_failed` | Ca access token va refresh token deu het han hoac bi thu hoi | Truy cap lai `http://localhost:8000/api/v1/tiktok/auth` de thuc hien uy quyen moi |
| `State khong hop le` | Binh luan callback sau 10 phut hoac mo tab gia lap | Thuc hien lai luong tu `GET /api/v1/tiktok/auth` de tao state hop le moi |

