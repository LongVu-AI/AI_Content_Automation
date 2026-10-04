# Kịch bản kiểm thử Bước 2

| Mã test | Nội dung | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| TC-01 | GET /health | HTTP 200, status=ok | Chưa thực hiện |
| TC-02 | POST /api/v1/content/intake hợp lệ | HTTP 200, success=true | Chưa thực hiện |
| TC-03 | POST /api/v1/content/intake thiếu content_id | HTTP 422/400 | Chưa thực hiện |
| TC-04 | GET /api/v1/content/{content_id} | HTTP 200, mock data | Chưa thực hiện |
| TC-05 | Postman Collection Run | Tất cả test pass | Chưa thực hiện |
| TC-06 | n8n gọi POST /api/v1/content/intake | n8n nhận JSON hợp lệ | Chưa thực hiện |
| TC-07 | Mở /docs | Swagger UI hiển thị đủ endpoint | Chưa thực hiện |

