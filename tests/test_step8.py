import sys
import time
import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE_URL = "http://localhost:8000"
SAMPLE_VIDEO_URL = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"

def setup_test_record(request_id: str) -> bool:
    """Tao ban ghi test trong Notion DB truoc khi publish."""
    print(f"\n[INFO] Tao ban ghi test: {request_id}")
    url = f"{BASE_URL}/api/v1/content/ai-output"
    payload = {
        "request_id": request_id,
        "status": "APPROVED",
        "ai_result": {
            "hook_text": "Video Test Buoc 8 TikTok Upload",
            "post_caption": "Tu dong hoa dang video TikTok #AI #Automation",
            "qc_score": 9.2,
            "qc_feedback": "Dat tieu chuan dang bai"
        },
        "metadata": {
            "processing_time_seconds": 12,
            "model_used": "gpt-4o"
        }
    }
    try:
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200 and res.json().get("success"):
            print(f"[PASS] Ban ghi {request_id} da duoc tao trong Notion DB.")
            return True
        print(f"[FAIL] Khong the tao ban ghi test: {res.text}")
        return False
    except Exception as e:
        print(f"[FAIL] Loi tao ban ghi test: {e}")
        return False

def test_tiktok_status() -> bool:
    """Kiem tra ket noi voi TikTok OAuth."""
    print("\n--- Test 0: Kiem tra TikTok OAuth Connection ---")
    url = f"{BASE_URL}/api/v1/tiktok/status"
    try:
        res = requests.get(url, timeout=10)
        assert res.status_code == 200, f"Expected 200, got: {res.status_code}"
        data = res.json()
        print(f"Status response: {data}")
        connected = data.get("data", {}).get("connected")
        assert connected is True, "TikTok chua duoc ket noi! Vui long chay Step 7 truoc."
        print("[PASS] TikTok OAuth ket noi thanh cong.")
        return True
    except Exception as e:
        print(f"[FAIL] Kiem tra ket noi TikTok that bai: {e}")
        return False

def test_publish_from_url(request_id: str) -> str:
    """Test 1: POST /publish-from-url voi video URL mau."""
    print("\n--- Test 1: POST /api/v1/tiktok/publish-from-url ---")
    url = f"{BASE_URL}/api/v1/tiktok/publish-from-url"
    payload = {
        "request_id": request_id,
        "video_url": SAMPLE_VIDEO_URL,
        "title": "Step 8 Test Video #Automation",
        "privacy_level": "SELF_ONLY"
    }
    try:
        res = requests.post(url, json=payload, timeout=30)
        assert res.status_code == 200, f"Expected 200, got: {res.status_code}"
        body = res.json()
        print(f"Publish response: {body}")

        assert body.get("success") is True, f"Expected success=True, got: {body}"
        publish_id = body.get("data", {}).get("publish_id")
        assert publish_id, "Response thieu publish_id"
        assert body.get("data", {}).get("status") == "PUBLISHING", "Status ban dau phai la PUBLISHING"

        print(f"[PASS] Khoi tao publish thanh cong. publish_id = {publish_id}")
        return publish_id
    except Exception as e:
        print(f"[FAIL] Test 1 that bai: {e}")
        return ""

def test_check_status(request_id: str) -> bool:
    """Test 2: POST /check-status de kiem tra trang thai publish tu TikTok."""
    print("\n--- Test 2: POST /api/v1/tiktok/check-status ---")
    url = f"{BASE_URL}/api/v1/tiktok/check-status"
    payload = {
        "request_id": request_id
    }
    try:
        res = requests.post(url, json=payload, timeout=20)
        assert res.status_code == 200, f"Expected 200, got: {res.status_code}"
        body = res.json()
        print(f"Check status response: {body}")

        assert body.get("success") is True, f"Expected success=True, got: {body}"
        data = body.get("data", {})
        assert data.get("request_id") == request_id, "request_id khong khop"
        assert "tiktok_status" in data, "Thieu tiktok_status trong response"
        assert "new_status" in data, "Thieu new_status trong response"

        print(f"[PASS] Kiem tra status thanh cong. TikTok status: {data.get('tiktok_status')}, Notion status: {data.get('new_status')}")
        return True
    except Exception as e:
        print(f"[FAIL] Test 2 that bai: {e}")
        return False

def test_verify_notion_db(request_id: str, expected_publish_id: str) -> bool:
    """Test 3: Kiem tra Notion DB page da duoc cap nhat tiktok_publish_id."""
    print("\n--- Test 3: Kiem tra Notion DB cap nhat tiktok_publish_id ---")
    url = f"{BASE_URL}/api/v1/content/{request_id}"
    try:
        res = requests.get(url, timeout=15)
        assert res.status_code == 200, f"Expected 200, got: {res.status_code}"
        body = res.json()
        print(f"Notion content response: {body}")

        data = body.get("data", {})
        actual_publish_id = data.get("tiktok_publish_id")
        actual_status = data.get("status")

        assert actual_publish_id == expected_publish_id, f"Expected publish_id={expected_publish_id}, got: {actual_publish_id}"
        assert actual_status in ["PUBLISHING", "PUBLISHED", "FAILED"], f"Status khong hop le sau khi publish: {actual_status}"

        print(f"[PASS] Notion DB da luu dung tiktok_publish_id: {actual_publish_id}, status: {actual_status}")
        return True
    except Exception as e:
        print(f"[FAIL] Test 3 that bai: {e}")
        return False

def test_file_upload_whitelist_security() -> bool:
    """Test 4: Kiem tra co che bao mat whitelist duong dan file upload."""
    print("\n--- Test 4: Kiem tra bao mat whitelist file upload ---")
    url = f"{BASE_URL}/api/v1/tiktok/publish-from-file"
    payload = {
        "request_id": "test_security_001",
        "video_path": "C:/Windows/System32/drivers/etc/hosts",
        "title": "Security test"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        body = res.json()
        print(f"Security test response: {body}")
        assert body.get("success") is False, "He thong khong duoc phep upload file ngoai whitelist"
        print("[PASS] Co che whitelist da chan thanh cong duong dan khong hop le.")
        return True
    except Exception as e:
        print(f"[FAIL] Test 4 that bai: {e}")
        return False

def test_webhook_endpoint() -> bool:
    """Test 5: Kiem tra endpoint webhook TikTok tiep nhan event."""
    print("\n--- Test 5: Kiem tra webhook endpoint ---")
    url = f"{BASE_URL}/api/v1/tiktok/webhook"
    payload = {
        "event": "video.publish.status",
        "data": {
            "publish_id": "mock_publish_id_123",
            "status": "PUBLISH_COMPLETE"
        }
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        assert res.status_code == 200, f"Expected 200, got: {res.status_code}"
        body = res.json()
        print(f"Webhook response: {body}")
        assert body.get("status") == "ok", "Webhook phai tra ve status: ok"
        print("[PASS] Webhook endpoint hoat dong dung tieu chuan.")
        return True
    except Exception as e:
        print(f"[FAIL] Test 5 that bai: {e}")
        return False

def main():
    print("==================================================")
    print("BAT DAU KIEM TRA TU DONG STEP 8 - TIKTOK PUBLISH")
    print("==================================================")

    # 1. Kiem tra ket noi TikTok OAuth
    if not test_tiktok_status():
        print("\n[ABORT] Dung kiem tra do TikTok OAuth chua ket noi.")
        sys.exit(1)

    # 2. Tao ban ghi test
    test_id = f"vid_test_step8_{int(time.time())}"
    if not setup_test_record(test_id):
        print("\n[ABORT] Khong the chuan bi ban ghi test.")
        sys.exit(1)

    # 3. Test publish tu URL
    publish_id = test_publish_from_url(test_id)
    if not publish_id:
        print("\n[ABORT] Dung kiem tra do Test 1 that bai.")
        sys.exit(1)

    # 4. Test kiem tra status
    t2 = test_check_status(test_id)

    # 5. Verify Notion DB
    t3 = test_verify_notion_db(test_id, publish_id)

    # 6. Test security whitelist
    t4 = test_file_upload_whitelist_security()

    # 7. Test webhook
    t5 = test_webhook_endpoint()

    print("\n==================================================")
    if all([publish_id != "", t2, t3, t4, t5]):
        print("[SUCCESS] TAT CA CAC TEST STEP 8 DEU PASS!")
    else:
        print("[ERROR] CO TEST THAT BAI TRONG STEP 8.")
    print("==================================================")

if __name__ == "__main__":
    main()

