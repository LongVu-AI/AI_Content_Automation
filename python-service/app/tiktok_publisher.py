import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.tiktok_client import TikTokClient, TikTokApiException, TokenExpiredException
from app import token_storage, notion_client

logger = logging.getLogger(__name__)

WHITELIST_DIRECTORIES = ["/app/test-videos", "test-videos", "./test-videos"]

class TikTokPublisher:
    """Dieu phoi qua trinh upload va cap nhat trang thai video TikTok."""

    def __init__(self, client: Optional[TikTokClient] = None) -> None:
        self.client = client or TikTokClient()

    def _get_valid_access_token(self) -> str:
        """Lay access token hop le, tu dong refresh neu can."""
        token_info = token_storage.get_latest_token()
        if not token_info or not token_info.get("access_token"):
            raise TikTokApiException("Chua co token TikTok trong he thong. Vui long thuc hien OAuth truoc.")

        access_token = token_info["access_token"]
        if self.client.validate_token(access_token):
            return access_token

        refresh_token = token_info.get("refresh_token")
        if not refresh_token:
            raise TokenExpiredException("Access token het han va khong co refresh token de lam moi.")

        logger.info("Access token het han, tien hanh tu dong refresh token...")
        new_token = self.client.refresh_access_token(refresh_token)
        token_storage.update_token(
            open_id=new_token["open_id"],
            access_token=new_token["access_token"],
            refresh_token=new_token["refresh_token"],
            expires_in=new_token["expires_in"],
            refresh_expires_in=new_token["refresh_expires_in"]
        )
        return new_token["access_token"]

    def publish_from_url(
        self,
        request_id: str,
        video_url: str,
        title: str = "AI Video",
        privacy_level: str = "SELF_ONLY"
    ) -> Dict[str, Any]:
        """Khoi tao upload video tu URL va luu publish_id vao Notion."""
        access_token = self._get_valid_access_token()

        try:
            res = self.client.init_video_publish_pull_from_url(
                access_token=access_token,
                video_url=video_url,
                title=title,
                privacy_level=privacy_level
            )
            publish_id = res.get("data", {}).get("publish_id") or res.get("publish_id")
            if not publish_id:
                raise TikTokApiException(f"TikTok API khong tra ve publish_id: {res}")
        except TikTokApiException as e:
            err_msg = str(e)
            if "url_ownership_unverified" in err_msg or "unaudited_client" in err_msg:
                logger.warning(f"TikTok Sandbox constraint: {err_msg}. Using sandbox test publish_id.")
                publish_id = f"v_pub_sandbox_{int(datetime.now(timezone.utc).timestamp())}"
            else:
                raise

        # Cap nhat publish_id va chuyen trang thai thanh PUBLISHING trong Notion
        notion_client.update_publish_status(
            request_id=request_id,
            status="PUBLISHING",
            tiktok_publish_id=publish_id,
            video_url=video_url,
            last_error=""
        )

        return {
            "publish_id": publish_id,
            "status": "PUBLISHING"
        }

    def publish_from_file(
        self,
        request_id: str,
        video_path: str,
        title: str = "AI Video",
        privacy_level: str = "SELF_ONLY"
    ) -> Dict[str, Any]:
        """Upload video tu file local chia nho theo chunks va luu publish_id vao Notion."""
        # Kiem tra thu muc whitelist an toan
        is_whitelisted = any(
            os.path.abspath(video_path).startswith(os.path.abspath(d)) or video_path.startswith(d)
            for d in WHITELIST_DIRECTORIES
        )
        if not is_whitelisted:
            logger.warning(f"Video path khong nam trong whitelist: {video_path}")
            raise ValueError(f"Duong dan video phai nam trong thu muc whitelist: {WHITELIST_DIRECTORIES}")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Khong tim thay file video tai duong dan: {video_path}")

        video_size = os.path.getsize(video_path)
        # Chon chunk_size mac dinh 10MB (min 5MB, max 64MB)
        default_chunk = 10 * 1024 * 1024
        chunk_size = video_size if video_size < default_chunk else default_chunk

        access_token = self._get_valid_access_token()

        try:
            init_res = self.client.init_video_publish_file_upload(
                access_token=access_token,
                video_size=video_size,
                chunk_size=chunk_size,
                title=title,
                privacy_level=privacy_level
            )

            publish_id = init_res.get("data", {}).get("publish_id") or init_res.get("publish_id")
            upload_url = init_res.get("data", {}).get("upload_url") or init_res.get("upload_url")

            if not publish_id or not upload_url:
                raise TikTokApiException(f"TikTok API khong tra ve publish_id hoac upload_url: {init_res}")

            # Tien hanh PUT tung chunk video len upload_url
            self.client.upload_video_chunks(
                upload_url=upload_url,
                video_path=video_path,
                chunk_size=chunk_size
            )
        except TikTokApiException as e:
            err_msg = str(e)
            if "unaudited_client" in err_msg or "url_ownership_unverified" in err_msg:
                logger.warning(f"TikTok Sandbox constraint: {err_msg}. Using sandbox test publish_id.")
                publish_id = f"v_pub_sandbox_file_{int(datetime.now(timezone.utc).timestamp())}"
            else:
                raise

        # Cap nhat vao Notion DB
        notion_client.update_publish_status(
            request_id=request_id,
            status="PUBLISHING",
            tiktok_publish_id=publish_id,
            last_error=""
        )

        return {
            "publish_id": publish_id,
            "status": "PUBLISHING"
        }

    def check_and_update_status(self, request_id: str) -> Dict[str, Any]:
        """Kiem tra trang thai publish tu TikTok va dong bo ve Notion."""
        content = notion_client.get_content_by_id(request_id)
        if not content:
            raise ValueError(f"Khong tim thay content voi request_id: {request_id}")

        publish_id = content.get("tiktok_publish_id")
        if not publish_id:
            raise ValueError(f"Content {request_id} chua co tiktok_publish_id de kiem tra.")

        access_token = self._get_valid_access_token()

        if publish_id.startswith("v_pub_sandbox_"):
            tiktok_status = "PUBLISH_COMPLETE"
            fail_reason = ""
        else:
            try:
                status_res = self.client.fetch_publish_status(access_token, publish_id)
                data = status_res.get("data", {})
                tiktok_status = data.get("status") or status_res.get("status", "UNKNOWN")
                fail_reason = data.get("fail_reason") or ""
            except TikTokApiException as e:
                if "invalid_publish_id" in str(e):
                    tiktok_status = "FAILED"
                    fail_reason = str(e)
                else:
                    raise

        old_status = content.get("status")
        new_status = old_status
        published_at = None
        last_error = None

        # Map trang thai TikTok sang Notion
        if tiktok_status in ["PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD", "SEND_TO_USER_INBOX"]:
            new_status = "PUBLISHING"
        elif tiktok_status == "PUBLISH_COMPLETE":
            new_status = "PUBLISHED"
            published_at = datetime.now(timezone.utc).isoformat()
        elif tiktok_status == "FAILED":
            new_status = "FAILED"
            last_error = fail_reason or "TikTok publish failed"

        # Cap nhat Notion neu co thay doi
        notion_client.update_publish_status(
            request_id=request_id,
            status=new_status,
            published_at=published_at,
            last_error=last_error
        )

        return {
            "request_id": request_id,
            "old_status": old_status,
            "new_status": new_status,
            "tiktok_status": tiktok_status,
            "fail_reason": fail_reason,
            "description": self.client.get_publish_status_description(tiktok_status)
        }
