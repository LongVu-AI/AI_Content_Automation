import os
import sys
import time
from datetime import datetime, timezone, timedelta
import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

BASE_URL = "http://localhost:8000"
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

if not NOTION_TOKEN or not NOTION_DATABASE_ID:
    print("[ERROR] Lỗi: Thiếu NOTION_TOKEN hoặc NOTION_DATABASE_ID trong .env")
    sys.exit(1)

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def upsert_test_item(request_id: str, scheduled_at_iso: str):
    """Tìm hoặc tạo bản ghi test trong Notion với status = APPROVED, locked_by rỗng"""
    query_url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "request_id",
            "title": {"equals": request_id}
        }
    }
    r = requests.post(query_url, headers=NOTION_HEADERS, json=payload)
    if r.status_code != 200:
        raise Exception(f"Lỗi query Notion DB: {r.text}")
    
    results = r.json().get("results", [])
    props = {
        "request_id": {"title": [{"text": {"content": request_id}}]},
        "status": {"select": {"name": "APPROVED"}},
        "scheduled_at": {"date": {"start": scheduled_at_iso}},
        "locked_by": {"rich_text": []},
        "locked_at": {"date": None},
        "product_name": {"rich_text": [{"text": {"content": f"Test Item {request_id}"}}]}
    }
    
    if results:
        page_id = results[0]["id"]
        update_url = f"https://api.notion.com/v1/pages/{page_id}"
        ru = requests.patch(update_url, headers=NOTION_HEADERS, json={"properties": props})
        if ru.status_code != 200:
            raise Exception(f"Lỗi update Notion page {request_id}: {ru.text}")
        return page_id
    else:
        create_url = "https://api.notion.com/v1/pages"
        rc = requests.post(create_url, headers=NOTION_HEADERS, json={
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": props
        })
        if rc.status_code != 200:
            raise Exception(f"Lỗi create Notion page {request_id}: {rc.text}")
        return rc.json()["id"]

def run_tests():
    print("=" * 60)
    print("[START] BẮT ĐẦU CHẠY TEST TỰ ĐỘNG BƯỚC 6 (Scheduling & Locking)")
    print("=" * 60)
    
    test_results = {}
    item1_id = "vid_test_step6_001"
    item2_id = "vid_test_step6_002"
    
    # -------------------------------------------------------------
    # BƯỚC 1: Tạo 2 bản ghi test trong Notion với status = APPROVED, scheduled_at = 5 phút trước
    # -------------------------------------------------------------
    print("\n[Bước 1] Tạo/Reset 2 bản ghi test trong Notion...")
    try:
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        p1 = upsert_test_item(item1_id, past_time)
        p2 = upsert_test_item(item2_id, past_time)
        print(f"  [OK] Đã chuẩn bị {item1_id} (page: {p1}) và {item2_id} (page: {p2})")
        test_results["Bước 1: Chuẩn bị 2 bản ghi Notion"] = "PASS"
    except Exception as e:
        print(f"  [ERROR] Thất bại: {e}")
        test_results["Bước 1: Chuẩn bị 2 bản ghi Notion"] = f"FAIL ({e})"
        return test_results

    # -------------------------------------------------------------
    # BƯỚC 2: Gọi GET /scheduled-due → verify có ít nhất 2 items
    # -------------------------------------------------------------
    print("\n[Bước 2] Gọi GET /api/v1/content/scheduled-due...")
    try:
        r = requests.get(f"{BASE_URL}/api/v1/content/scheduled-due")
        data = r.json()
        items = data.get("data", {}).get("items", [])
        req_ids = [it.get("request_id") for it in items]
        print(f"  -> Nhận được {len(items)} items: {req_ids}")
        
        assert r.status_code == 200, f"Status code: {r.status_code}"
        assert data.get("success") is True, f"Success flag: {data.get('success')}"
        assert item1_id in req_ids, f"{item1_id} không có trong scheduled-due"
        assert item2_id in req_ids, f"{item2_id} không có trong scheduled-due"
        print("  [OK] Verify thành công 2 test items xuất hiện trong scheduled-due")
        test_results["Bước 2: GET /scheduled-due"] = "PASS"
    except Exception as e:
        print(f"  [ERROR] Thất bại: {e}")
        test_results["Bước 2: GET /scheduled-due"] = f"FAIL ({e})"

    # -------------------------------------------------------------
    # BƯỚC 3: Gọi POST /lock cho item 1 với execution_id = "test_exec_001" → verify locked = true
    # -------------------------------------------------------------
    print(f"\n[Bước 3] Gọi POST /api/v1/content/{item1_id}/lock (test_exec_001)...")
    try:
        r = requests.post(
            f"{BASE_URL}/api/v1/content/{item1_id}/lock",
            json={"execution_id": "test_exec_001"}
        )
        data = r.json()
        print(f"  -> Response: {data}")
        assert r.status_code == 200, f"Status code: {r.status_code}"
        assert data.get("success") is True, "Success should be True"
        assert data.get("data", {}).get("locked") is True, "locked must be True"
        print("  [OK] Khóa thành công (locked = True)")
        test_results["Bước 3: POST /lock lần 1 (Lock thành công)"] = "PASS"
    except Exception as e:
        print(f"  [ERROR] Thất bại: {e}")
        test_results["Bước 3: POST /lock lần 1 (Lock thành công)"] = f"FAIL ({e})"

    # -------------------------------------------------------------
    # BƯỚC 4: Gọi POST /lock cùng item 1 với execution_id = "test_exec_002" → verify locked = false
    # -------------------------------------------------------------
    print(f"\n[Bước 4] Gọi POST /api/v1/content/{item1_id}/lock lại (test_exec_002 - Kiểm tra chống đè lock)...")
    try:
        r = requests.post(
            f"{BASE_URL}/api/v1/content/{item1_id}/lock",
            json={"execution_id": "test_exec_002"}
        )
        data = r.json()
        print(f"  -> Response: {data}")
        assert data.get("success") is False, "Success should be False"
        assert data.get("data", {}).get("locked") is False, "locked must be False"
        assert data.get("data", {}).get("reason") == "already_processed", f"Reason was: {data.get('data', {}).get('reason')}"
        assert data.get("error", {}).get("code") == "LOCK_FAILED", "Error code should be LOCK_FAILED"
        print("  [OK] Chặn lock trùng lặp thành công (locked = False, reason = already_processed)")
        test_results["Bước 4: POST /lock lần 2 (Chống xung đột)"] = "PASS"
    except Exception as e:
        print(f"  [ERROR] Thất bại: {e}")
        test_results["Bước 4: POST /lock lần 2 (Chống xung đột)"] = f"FAIL ({e})"

    # -------------------------------------------------------------
    # BƯỚC 5: Gọi POST /publish cho item 1 → verify status = PUBLISHING
    # -------------------------------------------------------------
    print(f"\n[Bước 5] Gọi POST /api/v1/content/{item1_id}/publish (test_exec_001)...")
    try:
        r = requests.post(
            f"{BASE_URL}/api/v1/content/{item1_id}/publish",
            json={"execution_id": "test_exec_001"}
        )
        data = r.json()
        print(f"  -> Response: {data}")
        assert data.get("success") is True, "Publish response success should be True"
        
        # Verify lại trên Notion qua endpoint get_content
        rg = requests.get(f"{BASE_URL}/api/v1/content/{item1_id}")
        get_data = rg.json()
        current_status = get_data.get("data", {}).get("status")
        print(f"  -> Status sau publish trong Notion: {current_status}")
        assert current_status == "PUBLISHING", f"Status in Notion must be PUBLISHING, but got: {current_status}"
        print("  [OK] Cập nhật PUBLISHING thành công")
        test_results["Bước 5: POST /publish (Chuyển trạng thái PUBLISHING)"] = "PASS"
    except Exception as e:
        print(f"  [ERROR] Thất bại: {e}")
        test_results["Bước 5: POST /publish (Chuyển trạng thái PUBLISHING)"] = f"FAIL ({e})"

    # -------------------------------------------------------------
    # BƯỚC 6: In kết quả
    # -------------------------------------------------------------
    print("\n" + "=" * 60)
    print("[REPORT] KẾT QUẢ TỔNG HỢP KIỂM THỬ BƯỚC 6")
    print("=" * 60)
    all_passed = True
    for step, res in test_results.items():
        print(f"- {step}: {res}")
        if res != "PASS":
            all_passed = False
            
    print("=" * 60)
    if all_passed:
        print("[SUCCESS] TẤT CẢ 5 BƯỚC TEST ĐỀU PASS 100%! HỆ THỐNG ĐÃ SẴN SÀNG.")
    else:
        print("[WARNING] CÓ TEST THẤT BẠI. VUI LÒNG KIỂM TRA LẠI.")
    print("=" * 60)
    return test_results

if __name__ == "__main__":
    run_tests()
