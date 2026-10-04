# API Contract (Bước 3)

## Tổng quan
- FastAPI đã kết nối thành công với Notion API (Master Database).
- Base URL, versioning và response envelope giữ nguyên như Bước 2.

## Cập nhật Endpoints

### 1. GET `/api/v1/content/{content_id}`
Đã thay thế mock data. Giờ đây endpoint này trả về dữ liệu thật query từ Notion database dựa theo `content_id`.
- **Response**: Trả về object content hoặc lỗi `CONTENT_NOT_FOUND` nếu không tìm thấy.
- **Lỗi hệ thống Notion**: Trả về `NOTION_API_ERROR`.

### 2. GET `/api/v1/content?limit={limit}&cursor={cursor}` (Mới)
Lấy danh sách các nội dung từ Notion database.
- **Query params**:
  - `limit`: Số lượng bản ghi tối đa trả về (mặc định 20, 1-100).
  - `cursor`: Chuỗi cursor để phân trang (lấy từ `next_cursor` của request trước).
- **Response**: Trả về mảng `items` cùng với `next_cursor` và `has_more`.

## Schema chuẩn trả về của một Content
```json
{
  "content_id": "string",
  "title": "string",
  "status": "string",
  "scheduled_at": "string | null",
  "video_url": "string | null",
  "caption": "string",
  "source": "string"
}
```
