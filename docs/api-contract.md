# API Contract (Cập nhật Schema mới)

## Tổng quan
- FastAPI kết nối với Notion API.
- Schema mới: 20 trường thông tin (fields).

## Schema chuẩn trả về của một Content (20 fields)
```json
{
  "request_id": "string",
  "product_name": "string",
  "product_link": "string | null",
  "brand_name": "string | null",
  "hook_text": "string | null",
  "voice_over_text": "string | null",
  "text_on_screen": "string | null",
  "image_prompt_en": "string | null",
  "bgm_vibe": "string | null",
  "post_caption": "string | null",
  "hashtags": "string | null",
  "qc_score": "number | null",
  "qc_feedback": "string | null",
  "video_url": "string | null",
  "status": "string | null",
  "scheduled_at": "string | null",
  "published_at": "string | null",
  "tiktok_publish_id": "string | null",
  "retry_count": "number | null",
  "last_error": "string | null"
}
```

## Endpoints

### 1. GET `/health`
Check health trạng thái dịch vụ.

### 2. POST `/api/v1/content/intake`
Tiếp nhận nội dung mới theo schema. Yêu cầu có `request_id` và `product_name`. Không bao gồm các field quản lý trạng thái tự động (status, scheduled_at, etc.).

### 3. GET `/api/v1/content/{request_id}`
Lấy data của 1 request id từ Notion API.
- Lỗi không tìm thấy → error.code = `CONTENT_NOT_FOUND`.

### 4. GET `/api/v1/content?limit={limit}&cursor={cursor}`
Liệt kê danh sách content. Trả về `items`, `next_cursor`, `has_more`.
