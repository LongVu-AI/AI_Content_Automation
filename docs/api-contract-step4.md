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
