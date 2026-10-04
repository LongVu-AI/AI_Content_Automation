# Kịch bản kiểm thử Bước 3 (Cập nhật Schema)

| Mã test | Nội dung | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| TC-01 | GET /api/v1/content/{request_id} (có thật) | HTTP 200, success=true, trả về đúng 20 field schema | Chưa thực hiện |
| TC-02 | GET /api/v1/content/INVALID_ID | HTTP 200, success=false, error=CONTENT_NOT_FOUND | Chưa thực hiện |
| TC-03 | GET /api/v1/content?limit=5 | HTTP 200, success=true, items trả về list dictionary | Chưa thực hiện |
| TC-04 | POST /api/v1/content/intake | HTTP 200, success=true, data chứa request_id | Chưa thực hiện |
| TC-05 | Kiểm tra log warning khi thiếu field Notion | Log "Thiếu cột ... trong Notion DB" hiện trên terminal Docker | Chưa thực hiện |
