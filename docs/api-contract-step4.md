# API Contract (Bước 4)

## Endpoints Mới

### 5. POST `/api/v1/content/ai-output`
Nhận payload từ AI Agent (qua n8n) và lưu kết quả vào Notion Database.

#### Payload Request
```json
{
  "request_id": "string",
  "status": "string",
  "ai_result": {
    "hook_text": "string",
    "voice_over_text": "string",
    "text_on_screen": "string",
    "image_prompt_en": "string",
    "bgm_vibe": "string",
    "post_caption": "string",
    "hashtags": ["#tag1", "#tag2"],
    "qc_score": 9.5,
    "qc_feedback": "string",
    "retry_count": 0
  },
  "metadata": {
    "processing_time_seconds": 35,
    "model_used": "string",
    "created_at": "string (ISO8601)"
  },
  "error": null
}
```

#### Response (Envelope chuẩn)
```json
{
  "success": true,
  "data": {
    "request_id": "string",
    "notion_page_id": "string"
  },
  "error": null,
  "meta": {
    "request_id": "string (uuid)",
    "timestamp": "string (ISO8601)"
  }
}
```

#### Logic Xử lý
- Kiểm tra `request_id` trong Notion.
- Nếu tồn tại: Gọi API `PATCH /v1/pages/{page_id}` để update các trường tương ứng.
- Nếu chưa tồn tại: Gọi API `POST /v1/pages` tạo trang mới.
- Cột `status`: tự động map "success" -> "DRAFT", "failed" -> "FAILED".
- Mảng `hashtags` sẽ được join thành một chuỗi cách nhau bằng dấu cách (ví dụ "#tag1 #tag2") để lưu dưới dạng `rich_text`.

### 6. GET `/api/v1/content/pending-review`
Lấy danh sách các trang nội dung có status là `PENDING_REVIEW`.

#### Response
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "request_id": "string",
        "product_name": "string",
        "status": "PENDING_REVIEW",
        "...": "..."
      }
    ]
  },
  "error": null,
  "meta": {
    "request_id": "string",
    "timestamp": "string"
  }
}
```

### 7. PATCH `/api/v1/content/{request_id}/status`
Cập nhật trạng thái của nội dung.

#### Payload Request
```json
{
  "status": "APPROVED",
  "reviewed_by": "Long",
  "note": "OK duyet"
}
```
*Lưu ý: Các giá trị `status` hợp lệ: `APPROVED`, `NEEDS_REVISION`, `PUBLISHING`, `PUBLISHED`, `FAILED`, `SCHEDULED`.*

#### Response
```json
{
  "success": true,
  "data": {
    "request_id": "string",
    "status": "APPROVED",
    "updated_at": "string (ISO8601)"
  },
  "error": null,
  "meta": {
    "request_id": "string",
    "timestamp": "string"
  }
}
```
#### Logic Xử lý
- Kiểm tra `request_id` trong Notion.
- Nếu không tìm thấy, trả về lỗi `CONTENT_NOT_FOUND`.
- Nếu cập nhật thành công, thay đổi `status` thành giá trị mới.
- Nếu có truyền `reviewed_by` và `note`, nối chuỗi lại theo format `[REVIEWED by <reviewed_by>] <note>` và ghi vào trường `last_error` của Notion.
