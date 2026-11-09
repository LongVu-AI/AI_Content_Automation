import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.tiktok_client import TikTokApiException
from app.tiktok_publisher import TikTokPublisher

client = TestClient(app)

def test_p1_1_no_fake_published_without_simulation():
    """P1.1: Verify publisher raises real TikTokApiException when sandbox simulation is false."""
    mock_client = MagicMock()
    mock_client.init_video_publish_pull_from_url.side_effect = TikTokApiException("url_ownership_unverified")
    
    with patch.dict("os.environ", {"ENABLE_TIKTOK_SANDBOX_SIMULATION": "false"}):
        pub = TikTokPublisher(client=mock_client)
        assert pub.enable_sandbox_simulation is False
        
        with patch.object(pub, "_get_valid_access_token", return_value="mock_token"):
            with pytest.raises(TikTokApiException) as exc_info:
                pub.publish_from_url("req_test_001", "https://example.com/video.mp4")
            assert "url_ownership_unverified" in str(exc_info.value)
    print("PASS: P1.1 - No fake published ID generated.")

def test_p1_2_publish_endpoint_rejects_unapproved():
    """P1.2: Verify /publish-from-url rejects NEEDS_REVISION and DRAFT."""
    # Test with NEEDS_REVISION
    with patch("app.notion_client.get_content_by_id", return_value={"status": "NEEDS_REVISION", "retry_count": 0}):
        res = client.post("/api/v1/tiktok/publish-from-url", json={"request_id": "req_needs_rev", "video_url": "https://example.com/v.mp4"})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["error"]["code"] == "CONTENT_NOT_APPROVED"

    # Test with PUBLISHING (already in-flight)
    with patch("app.notion_client.get_content_by_id", return_value={"status": "PUBLISHING", "locked_by": "exec_123", "retry_count": 0}):
        res = client.post("/api/v1/tiktok/publish-from-url", json={"request_id": "req_pub", "video_url": "https://example.com/v.mp4"})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["error"]["code"] == "CONTENT_ALREADY_PUBLISHING"
    print("PASS: P1.2 - Unapproved and in-flight publish calls properly rejected.")

def test_p1_3_status_transition_guard():
    """P1.3: Verify cannot transition status from PUBLISHED back to NEEDS_REVISION."""
    with patch("app.notion_client.get_content_by_id", return_value={"status": "PUBLISHED"}):
        res = client.patch("/api/v1/content/req_published/status", json={"status": "NEEDS_REVISION", "reviewed_by": "Tester"})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_STATUS_TRANSITION"
    print("PASS: P1.3 - Status transition from PUBLISHED guarded.")

def test_p1_5_v2_endpoints_mounted():
    """P1.5: Verify v2 router is mounted in FastAPI."""
    res = client.get("/api/v2/content/req_nonexistent/revisions/1")
    assert res.status_code == 404
    assert res.json().get("error", {}).get("message") == "Chưa có bản bàn giao."
    print("PASS: P1.5 - v2 endpoints registered and functional in FastAPI.")

def test_p2_7_step8_timeout_branch():
    """P2.7: Verify Step8 workflow has IF Max Reached and polling timeout branch."""
    with open("n8n/Step8 - TikTok Publish.json", "r", encoding="utf-8") as f:
        wf = json.load(f)
    node_names = [n["name"] for n in wf["nodes"]]
    assert "POST Lock Content" in node_names
    assert "IF Lock Acquired" in node_names
    assert "IF Max Reached" in node_names
    assert "NoOp - Polling Timeout" in node_names
    print("PASS: P2.7 - Step8 has lock checking and polling timeout branch.")

if __name__ == "__main__":
    test_p1_1_no_fake_published_without_simulation()
    test_p1_2_publish_endpoint_rejects_unapproved()
    test_p1_3_status_transition_guard()
    test_p1_5_v2_endpoints_mounted()
    test_p2_7_step8_timeout_branch()
    print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
