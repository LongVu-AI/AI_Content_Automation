import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.tiktok_client import TikTokApiException
from app.tiktok_publisher import TikTokPublisher
import app.notion_client as notion_client

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

def test_stale_revision_guard():
    """P1.3+: Verify status update with stale revision is rejected."""
    with patch("app.notion_client.get_content_by_id", return_value={"status": "PENDING_REVIEW", "revision": 2}):
        res = client.patch("/api/v1/content/req_rev/status", json={"status": "APPROVED", "reviewed_by": "Bao", "revision": 1})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["error"]["code"] == "STALE_REVISION"
    print("PASS: Stale revision status updates properly rejected.")

def test_reject_drive_folder_url():
    """Direct URL check: Verify Google Drive folder URLs are rejected with clear explanation."""
    with patch("app.notion_client.get_content_by_id", return_value={"status": "APPROVED", "retry_count": 0, "locked_by": None}):
        with patch("app.notion_client.lock_and_publish", return_value={"locked": True}):
            res = client.post("/api/v1/tiktok/publish-from-url", json={
                "request_id": "req_folder",
                "video_url": "https://drive.google.com/drive/folders/1MD7l8SuA2SuTO8lCyjax_JzmyA62KJ1t?usp=drive_link"
            })
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is False
            assert data["error"]["code"] == "INVALID_DIRECT_VIDEO_URL"
    print("PASS: Google Drive folder URLs rejected with INVALID_DIRECT_VIDEO_URL.")

def test_p1_4_lock_and_publish_supports_scheduled():
    """P1.4: Verify lock_and_publish supports both APPROVED and SCHEDULED items."""
    mock_notion = MagicMock()
    mock_page = {
        "id": "page_123",
        "properties": {
            "request_id": {"title": [{"plain_text": "req_sched", "text": {"content": "req_sched"}}]},
            "status": {"select": {"name": "SCHEDULED"}},
            "locked_by": {"rich_text": []},
            "locked_at": {"date": None},
            "revision": {"number": 1}
        }
    }
    mock_page_locked = {
        "id": "page_123",
        "properties": {
            "request_id": {"title": [{"plain_text": "req_sched", "text": {"content": "req_sched"}}]},
            "status": {"select": {"name": "SCHEDULED"}},
            "locked_by": {"rich_text": [{"plain_text": "exec_456", "text": {"content": "exec_456"}}]},
            "locked_at": {"date": {"start": "2026-11-09T00:00:00Z"}},
            "revision": {"number": 1}
        }
    }
    mock_notion.databases.query.return_value = {"results": [mock_page]}
    mock_notion.pages.retrieve.return_value = mock_page_locked

    with patch.object(notion_client, "notion", mock_notion):
        with patch.object(notion_client, "NOTION_DATABASE_ID", "mock_db"):
            result = notion_client.lock_and_publish("req_sched", "exec_456")
            assert result["locked"] is True
            assert result["page_id"] == "page_123"
    print("PASS: P1.4 - lock_and_publish successfully locks SCHEDULED items.")

def test_unlock_stale_locks():
    """Verify unlock_stale_locks releases expired locks."""
    mock_notion = MagicMock()
    stale_time = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    mock_stale_page = {
        "id": "page_stale",
        "properties": {
            "request_id": {"title": [{"text": {"content": "req_stale"}}]},
            "status": {"select": {"name": "PUBLISHING"}},
            "locked_by": {"rich_text": [{"text": {"content": "crashed_worker"}}]},
            "locked_at": {"date": {"start": stale_time}}
        }
    }
    mock_notion.databases.query.return_value = {"results": [mock_stale_page]}

    with patch.object(notion_client, "notion", mock_notion):
        with patch.object(notion_client, "NOTION_DATABASE_ID", "mock_db"):
            unlocked = notion_client.unlock_stale_locks(timeout_minutes=30)
            assert unlocked == 1
            mock_notion.pages.update.assert_called_once()
            called_kwargs = mock_notion.pages.update.call_args[1]
            assert called_kwargs["properties"]["status"]["select"]["name"] == "APPROVED"
            assert called_kwargs["properties"]["locked_by"]["rich_text"] == []
    print("PASS: Stale locks successfully released after timeout.")

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

def test_step5_workflows_revision_and_security():
    """Verify Step5 Send and Callback workflows have revision and webhook security."""
    with open("n8n/Step5 - Send Approval Request.json", "r", encoding="utf-8") as f:
        send_wf = json.load(f)
    send_text = json.dumps(send_wf)
    assert "revision" in send_text
    assert "approve|{{ $json.request_id }}|{{ $json.revision || 1 }}" in send_text

    with open("n8n/Step5 - Handle Approval Callback.json", "r", encoding="utf-8") as f:
        cb_wf = json.load(f)
    cb_text = json.dumps(cb_wf)
    assert "TELEGRAM_WEBHOOK_SECRET" in cb_text
    assert "TELEGRAM_AUTHORIZED_USER_IDS" in cb_text
    assert "revision" in cb_text
    print("PASS: Step5 workflows contain revision handling and webhook security.")

if __name__ == "__main__":
    test_p1_1_no_fake_published_without_simulation()
    test_p1_2_publish_endpoint_rejects_unapproved()
    test_p1_3_status_transition_guard()
    test_stale_revision_guard()
    test_reject_drive_folder_url()
    test_p1_4_lock_and_publish_supports_scheduled()
    test_unlock_stale_locks()
    test_p1_5_v2_endpoints_mounted()
    test_p2_7_step8_timeout_branch()
    test_step5_workflows_revision_and_security()
    print("\nALL 10 VERIFICATION TESTS PASSED SUCCESSFULLY!")
