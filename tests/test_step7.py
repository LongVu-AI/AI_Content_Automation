import sys
import urllib.parse
import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE_URL = "http://localhost:8000"

def test_authorization_url() -> bool:
    """Test 1: Kiem tra format cua URL Authorization TikTok."""
    print("\n--- Test 1: Kiem tra URL Authorization ---")
    url = f"{BASE_URL}/api/v1/tiktok/auth"
    try:
        response = requests.get(url, allow_redirects=False, timeout=10)
        assert response.status_code in [302, 307], f"Expected 302 or 307 redirect, got: {response.status_code}"
        
        location = response.headers.get("Location", "")
        print(f"Location header: {location}")
        
        assert location.startswith("https://www.tiktok.com/v2/auth/authorize/"), "URL redirect khong bat dau bang endpoint authorize cua TikTok v2"
        
        parsed = urllib.parse.urlparse(location)
        query_params = urllib.parse.parse_qs(parsed.query)
        
        assert "client_key" in query_params, "Thieu client_key trong URL"
        assert "scope" in query_params, "Thieu scope trong URL"
        assert "response_type" in query_params and query_params["response_type"][0] == "code", "response_type phai la 'code'"
        assert "redirect_uri" in query_params, "Thieu redirect_uri trong URL"
        assert "state" in query_params, "Thieu state de chong CSRF trong URL"
        
        print("[PASS] URL Authorization hop le, day du params.")
        return True
    except Exception as e:
        print(f"[FAIL] Test 1 that bai: {e}")
        return False

def test_mock_callback_error_handling() -> bool:
    """Test 2: Kiem tra xu ly loi callback khi code/state khong hop le."""
    print("\n--- Test 2: Kiem tra callback voi ma gia (Error Handling) ---")
    try:
        # Truong hop 2a: State gia mao (khong ton tai trong session)
        invalid_url = f"{BASE_URL}/api/v1/tiktok/callback?code=mock_code&state=fake_state_123"
        res_invalid = requests.get(invalid_url, timeout=10)
        assert res_invalid.status_code == 400, f"Expected 400 for invalid state, got: {res_invalid.status_code}"
        print("  -> Chank state khong hop le thanh cong (HTTP 400).")

        # Truong hop 2b: State hop le nhung code gia goi den TikTok
        auth_res = requests.get(f"{BASE_URL}/api/v1/tiktok/auth", allow_redirects=False, timeout=10)
        location = auth_res.headers.get("Location", "")
        parsed = urllib.parse.urlparse(location)
        query_params = urllib.parse.parse_qs(parsed.query)
        valid_state = query_params["state"][0]
        
        callback_url = f"{BASE_URL}/api/v1/tiktok/callback?code=fake_test_code_999&state={valid_state}"
        res_callback = requests.get(callback_url, timeout=10)
        assert res_callback.status_code == 400, f"Expected 400 for invalid code exchange, got: {res_callback.status_code}"
        print("  -> Xu ly loi doi code gia thanh cong (HTTP 400).")

        print("[PASS] Endpoint callback bat loi dung tieu chuan.")
        return True
    except Exception as e:
        print(f"[FAIL] Test 2 that bai: {e}")
        return False

def test_status_when_not_authenticated() -> bool:
    """Test 3: Kiem tra GET /status khi chua co token hop le."""
    print("\n--- Test 3: Kiem tra GET /status khi chua ket noi ---")
    try:
        res = requests.get(f"{BASE_URL}/api/v1/tiktok/status", timeout=10)
        assert res.status_code == 200, f"Expected 200, got: {res.status_code}"
        data = res.json()
        print(f"Status response: {data}")
        
        assert data.get("success") is True, "Success envelope phai la True"
        connected = data.get("data", {}).get("connected")
        assert connected is False, f"Expected connected=False, got: {connected}"
        
        print("[PASS] Endpoint /status tra ve connected=False dung ky vong.")
        return True
    except Exception as e:
        print(f"[FAIL] Test 3 that bai: {e}")
        return False

def run_all_tests():
    print("=" * 60)
    print("BAT DAU KIEM THU STEP 7: TIKTOK OAUTH & STATUS API")
    print("=" * 60)

    results = {
        "Test 1: URL Authorization format": test_authorization_url(),
        "Test 2: Mock callback error handling": test_mock_callback_error_handling(),
        "Test 3: Status when unauthenticated": test_status_when_not_authenticated()
    }

    print("\n" + "=" * 60)
    print("TONG HOP KET QUA TEST STEP 7")
    print("=" * 60)
    all_pass = True
    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} - {name}")
        if not passed:
            all_pass = False

    print("=" * 60)
    if all_pass:
        print("TAT CA TEST DEU THANH CONG!")
    else:
        print("CO TEST THAT BAI!")
    print("=" * 60)

if __name__ == "__main__":
    run_all_tests()

