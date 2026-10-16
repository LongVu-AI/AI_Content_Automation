# API Contract (Bước 6) - Scheduling & Status Locking

## 1. Tổng quan cơ chế Status Locking (Khóa trạng thái lạc quan)
Khi hệ thống có nhiều cron runner chạy song song hoặc nhiều execution cùng lúc, nguy cơ **race condition** (hai runner cùng lấy 1 video và publish trùng lặp) có thể xảy ra.
Bước 6 thiết kế cơ chế **Status Locking** để đảm bảo tính tuần tự và an toàn:
1. **Lọc video đến giờ đăng**: Chỉ lấy video có `status = "APPROVED"`, `scheduled_at <= now` và `locked_by` còn trống.
2. **Khóa trạng thái (Locking)**: Worker gửi `execution_id` của mình đến endpoint `/lock`. Hệ thống kiểm tra điều kiện và cập nhật `status = "SCHEDULED"`, `locked_by = execution_id`, `locked_at = now`. Sau đó re-query để đảm bảo không bị worker khác ghi đè.
3. **Tiến hành đăng (Publishing)**: Khi đã lock thành công, worker chuyển trạng thái sang `PUBLISHING`.

---

## 2. Các thuộc tính mới trong Notion Database

| Tên cột | Kiểu dữ liệu Notion | Ý nghĩa |
|---|---|---|
| `locked_by` | Rich text (Text) | Lưu `execution_id` của n8n đang giữ quyền xử lý |
| `locked_at` | Date | Thời điểm lock bản ghi |

> **Hướng dẫn tạo thủ công (nếu cần):**
> Vào Notion Database → Thêm cột mới → Đặt tên `locked_by` (kiểu Text/Rich text) và cột `locked_at` (kiểu Date).

---

## 3. Chi tiết Endpoints

### 3.1. GET `/api/v1/content/scheduled-due`
Lấy danh sách các video đã duyệt (`APPROVED`) và đã đến giờ đăng (`scheduled_at <= now`) mà chưa bị lock (`locked_by is empty`).

#### Response
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "request_id": "vid_20261016_001",
        "product_name": "Sản phẩm A",
        "status": "APPROVED",
        "scheduled_at": "2026-10-16T10:00:00+00:00",
        "locked_by": null,
        "locked_at": null,
        "...": "..."
      }
    ]
  },
  "error": null,
  "meta": {
    "request_id": "uuid",
    "timestamp": "ISO8601"
  }
}
```

---

### 3.2. POST `/api/v1/content/{request_id}/lock`
Thực hiện khóa bản ghi cho một execution cụ thể.

#### Request Body
```json
{
  "execution_id": "exec_123456"
}
```

#### Logic Xử lý Atomic:
1. Tìm bản ghi theo `request_id`.
2. Kiểm tra: nếu `status != "APPROVED"` hoặc `locked_by` đã có giá trị → Trả về `{ "locked": false, "reason": "already_processed" }` (Lỗi `LOCK_FAILED`).
3. Cập nhật `status = "SCHEDULED"`, `locked_by = execution_id`, `locked_at = now`.
4. Re-query lại bản ghi để kiểm tra `locked_by`.
5. Nếu khớp `execution_id` → Trả về `{ "locked": true, "page_id": "..." }`.
6. Nếu không khớp (bị worker khác ghi đè) → Trả về `{ "locked": false, "reason": "race_lost" }`.

#### Response Thành công (HTTP 200)
```json
{
  "success": true,
  "data": {
    "locked": true,
    "page_id": "notion-page-id-uuid"
  },
  "error": null,
  "meta": {
    "request_id": "uuid",
    "timestamp": "ISO8601"
  }
}
```

#### Response Thất bại (HTTP 200, success = false)
```json
{
  "success": false,
  "data": {
    "locked": false,
    "reason": "already_processed"
  },
  "error": {
    "code": "LOCK_FAILED",
    "message": "Lock failed: already_processed"
  },
  "meta": {
    "request_id": "uuid",
    "timestamp": "ISO8601"
  }
}
```

---

### 3.3. POST `/api/v1/content/{request_id}/publish`
Chuyển trạng thái sang `PUBLISHING` sau khi đã lock thành công.

#### Request Body
```json
{
  "execution_id": "exec_123456"
}
```

#### Logic Xử lý:
1. Kiểm tra bản ghi phải có `locked_by == execution_id`.
2. Nếu thỏa mãn: cập nhật `status = "PUBLISHING"`.
3. Nếu không khớp lock: trả về lỗi `PUBLISH_FAILED`.

#### Response Thành công
```json
{
  "success": true,
  "data": {
    "success": true,
    "page_id": "notion-page-id-uuid"
  },
  "error": null,
  "meta": {
    "request_id": "uuid",
    "timestamp": "ISO8601"
  }
}
```

