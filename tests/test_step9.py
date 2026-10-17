import os
import sys
import time
import subprocess
from unittest.mock import patch, MagicMock
import requests
from dotenv import load_dotenv

load_dotenv()

# Dam bao encoding UTF-8 tren Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Them python-service vao sys.path de import cac module noi bo
current_dir = os.path.dirname(os.path.abspath(__file__))
python_service_dir = os.path.abspath(os.path.join(current_dir, "..", "python-service"))
if python_service_dir not in sys.path:
    sys.path.insert(0, python_service_dir)

from app.retry_helper import retry_on_failure
from app.notifier import send_telegram_alert, reset_rate_limit

BASE_URL = "http://localhost:8000"

def test_middleware_request_id() -> bool:
    """Test 1: Kiem tra middleware logging va header X-Request-ID."""
    print("\n--- Test 1: Middleware Logging & X-Request-ID Header ---")
    try:
        # Truong hop 1a: Client truyen X-Request-ID tu sinh
        custom_id = "test-custom-trace-999"
        res1 = requests.get(f"{BASE_URL}/health", headers={"X-Request-ID": custom_id}, timeout=10)
        assert res1.status_code == 200, f"Expected 200, got: {res1.status_code}"
        res1_id = res1.headers.get("X-Request-ID")
        assert res1_id == custom_id, f"Expected {custom_id}, got: {res1_id}"
        print(f"  -> X-Request-ID tuy bien duoc giu nguyen: {res1_id}")

        # Truong hop 1b: Client khong truyen, server tu sinh X-Request-ID
        res2 = requests.get(f"{BASE_URL}/health", timeout=10)
        assert res2.status_code == 200, f"Expected 200, got: {res2.status_code}"
        res2_id = res2.headers.get("X-Request-ID")
        assert res2_id and len(res2_id) > 10, f"Server khong sinh X-Request-ID hop le: {res2_id}"
        print(f"  -> Server tu sinh X-Request-ID: {res2_id}")

        print("[PASS] Test 1 thanh cong: Middleware da xu ly va phan hoi X-Request-ID chuan xac.")
        return True
    except Exception as e:
        print(f"[FAIL] Test 1 that bai: {e}")
        return False

def test_global_exception_handler() -> bool:
    """Test 2: Goi endpoint khong ton tai, kiem tra envelope loi chuan."""
    print("\n--- Test 2: Global Exception Handler cho endpoint 404 ---")
    try:
        url = f"{BASE_URL}/api/v1/non-existent-endpoint-random-12345"
        res = requests.get(url, timeout=10)
        assert res.status_code == 404, f"Expected 404, got: {res.status_code}"
        
        body = res.json()
        print(f"  Response body 404: {body}")

        assert body.get("success") is False, "success phai la False"
        assert body.get("data") is None, "data phai la None"
        assert "error" in body and body["error"].get("code") == "NOT_FOUND", "error.code phai la NOT_FOUND"
        assert "meta" in body and "request_id" in body["meta"], "meta phai co request_id"
        assert res.headers.get("X-Request-ID"), "Response header thieu X-Request-ID"

        print("[PASS] Test 2 thanh cong: Exception handler tra ve envelope loi dung chuan.")
        return True
    except Exception as e:
        print(f"[FAIL] Test 2 that bai: {e}")
        return False

def test_retry_helper_logic() -> bool:
    """Test 3: Kiem tra decorator retry_on_failure voi mock function."""
    print("\n--- Test 3: Kiem tra Retry Logic & Exponential Backoff ---")
    try:
        call_count = 0

        # Ham that bai 2 lan dau, lan 3 thanh cong
        @retry_on_failure(max_attempts=3, backoff_seconds=0.05, exceptions=(ValueError,))
        def flaky_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Loi gia dinh lan {call_count}")
            return x * 2

        result = flaky_function(21)
        assert result == 42, f"Expected 42, got {result}"
        assert call_count == 3, f"Expected 3 calls, got {call_count}"
        print(f"  -> Ham flaky da thu lai dung 3 lan va tra ve: {result}")

        # Kiem tra callback on_final_failure khi that bai toan bo
        final_failure_called = False
        def on_fail_cb(err, func_name, *args, **kwargs):
            nonlocal final_failure_called
            final_failure_called = True

        @retry_on_failure(max_attempts=2, backoff_seconds=0.05, exceptions=(RuntimeError,), on_final_failure=on_fail_cb)
        def always_fail():
            raise RuntimeError("Loi bat kha khang")

        try:
            always_fail()
        except RuntimeError:
            pass

        assert final_failure_called is True, "Callback on_final_failure khong duoc goi khi fail toan bo"
        print("  -> Callback on_final_failure da duoc goi dung khi qua max_attempts.")

        print("[PASS] Test 3 thanh cong: Co che retry va callback hoat dong dung thiet ke.")
        return True
    except Exception as e:
        print(f"[FAIL] Test 3 that bai: {e}")
        return False

def test_increment_retry_count_notion() -> bool:
    """Test 4: Kiem tra ham increment_retry_count trong Notion DB."""
    print("\n--- Test 4: Kiem tra increment_retry_count trong Notion DB ---")
    test_id = f"vid_test_retry_{int(time.time())}"
    try:
        # 1. Tao ban ghi ban dau trong Notion DB
        intake_url = f"{BASE_URL}/api/v1/content/ai-output"
        payload = {
            "request_id": test_id,
            "status": "FAILED",
            "ai_result": {
                "hook_text": "Video test increment_retry_count",
                "qc_score": 5.0,
                "retry_count": 0
            }
        }
        res_create = requests.post(intake_url, json=payload, timeout=15)
        assert res_create.status_code == 200 and res_create.json().get("success"), "Tao ban ghi test that bai"
        print(f"  -> Da tao ban ghi test: {test_id}")

        # 2. Goi increment_retry_count qua docker exec
        cmd = [
            "docker", "exec", "ai-automation-python",
            "python", "-c",
            f"from app import notion_client; print(notion_client.increment_retry_count('{test_id}'))"
        ]
        out = subprocess.check_output(cmd, text=True).strip()
        lines = [l.strip() for l in out.strip().splitlines() if l.strip().isdigit()]
        new_count = int(lines[-1]) if lines else 0
        assert new_count == 1, f"Expected retry_count=1, got: {new_count}"
        print(f"  -> increment_retry_count lan 1 tra ve: {new_count}")

        # 3. Goi them lan 2 de kiem tra gia tri tich luy
        out2 = subprocess.check_output(cmd, text=True).strip()
        lines2 = [l.strip() for l in out2.strip().splitlines() if l.strip().isdigit()]
        new_count2 = int(lines2[-1]) if lines2 else 0
        assert new_count2 == 2, f"Expected retry_count=2, got: {new_count2}"
        print(f"  -> increment_retry_count lan 2 tra ve: {new_count2}")

        # 4. Kiem tra lai tu GET endpoint
        res_get = requests.get(f"{BASE_URL}/api/v1/content/{test_id}", timeout=10)
        assert res_get.status_code == 200, f"Expected 200, got: {res_get.status_code}"
        data = res_get.json().get("data", {})
        assert data.get("retry_count") == 2, f"Expected retry_count trong Notion la 2, got: {data.get('retry_count')}"

        print("[PASS] Test 4 thanh cong: Cot retry_count trong Notion DB duoc tang gia tri chinh xac.")
        return True
    except Exception as e:
        print(f"[FAIL] Test 4 that bai: {e}")
        return False

def test_notifier_rate_limit() -> bool:
    """Test 5: Kiem tra notifier rate limit (10 lan goi, chi 5 tin duoc gui)."""
    print("\n--- Test 5: Kiem tra Notifier Rate Limit (toi da 5 tin / phut) ---")
    try:
        reset_rate_limit()

        # Mock requests.post va tokens de kiem tra logic rate limit ma khong gui spam toi Telegram
        with patch("app.notifier.TELEGRAM_BOT_TOKEN", "mock_token"), \
             patch("app.notifier.TELEGRAM_CHAT_ID", "mock_chat_id"), \
             patch("requests.post") as mock_post:
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.json.return_value = {"ok": True}
            mock_post.return_value = mock_res

            # Goi 10 lan lien tiep
            results = []
            for i in range(10):
                success = send_telegram_alert(
                    message=f"Test alert so {i+1}",
                    severity="WARNING",
                    request_id=f"req_{i+1}",
                    component="RateLimitUnitTest"
                )
                results.append(success)

            sent_count = sum(1 for r in results if r is True)
            blocked_count = sum(1 for r in results if r is False)

            print(f"  -> Tong so lan goi: 10")
            print(f"  -> So tin duoc phep gui: {sent_count}")
            print(f"  -> So tin bi rate limit chan: {blocked_count}")

            assert sent_count == 5, f"Expected 5 tin gui duoc, got {sent_count}"
            assert blocked_count == 5, f"Expected 5 tin bi chan, got {blocked_count}"
            assert mock_post.call_count == 5, f"Expected requests.post duoc goi dung 5 lan, got {mock_post.call_count}"

        print("[PASS] Test 5 thanh cong: Co che in-memory rate limit hoat dong chinh xac 5 tin/phut.")
        return True
    except Exception as e:
        print(f"[FAIL] Test 5 that bai: {e}")
        return False

def main():
    print("=" * 60)
    print("BAT DAU KIEM THU STEP 9: LOGGING, RETRY & NOTIFICATION")
    print("=" * 60)

    t1 = test_middleware_request_id()
    t2 = test_global_exception_handler()
    t3 = test_retry_helper_logic()
    t4 = test_increment_retry_count_notion()
    t5 = test_notifier_rate_limit()

    all_pass = all([t1, t2, t3, t4, t5])

    print("\n" + "=" * 60)
    print("TONG HOP KET QUA TEST STEP 9")
    print("=" * 60)
    print(f"Test 1 - Middleware X-Request-ID:     {'[PASS]' if t1 else '[FAIL]'}")
    print(f"Test 2 - Global Exception Handler:    {'[PASS]' if t2 else '[FAIL]'}")
    print(f"Test 3 - Retry Logic Backoff:         {'[PASS]' if t3 else '[FAIL]'}")
    print(f"Test 4 - Notion Increment Retry Count: {'[PASS]' if t4 else '[FAIL]'}")
    print(f"Test 5 - Notifier 5 msg/min Limit:    {'[PASS]' if t5 else '[FAIL]'}")
    print("=" * 60)

    if all_pass:
        print("[SUCCESS] TAT CA CAC TEST STEP 9 DEU PASS!")
        sys.exit(0)
    else:
        print("[ERROR] CO TEST THAT BAI TRONG STEP 9.")
        sys.exit(1)

if __name__ == "__main__":
    main()
