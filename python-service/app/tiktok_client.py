import os
import logging
import urllib.parse
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)

class TikTokApiException(Exception):
    """Loi co ban khi goi TikTok API."""
    pass

class TokenExpiredException(TikTokApiException):
    """Loi access token da het han (HTTP 401)."""
    pass

class RateLimitException(TikTokApiException):
    """Loi vuot qua gioi han luot goi TikTok API (HTTP 429)."""
    pass

class TikTokClient:
    """Client giao tiep voi TikTok Open API v2."""

    def __init__(
        self,
        client_key: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None
    ) -> None:
        self.client_key = client_key or os.getenv("TIKTOK_CLIENT_KEY", "")
        self.client_secret = client_secret or os.getenv("TIKTOK_CLIENT_SECRET", "")
        self.redirect_uri = redirect_uri or os.getenv("TIKTOK_REDIRECT_URI", "")

        if not self.client_key or not self.client_secret or not self.redirect_uri:
            logger.warning("Thieu bien moi truong TikTok OAuth: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET hoac TIKTOK_REDIRECT_URI.")

        self.oauth_base_url = "https://www.tiktok.com/v2/auth/authorize/"
        self.token_url = "https://open.tiktokapis.com/v2/oauth/token/"
        self.user_info_url = "https://open.tiktokapis.com/v2/user/info/"
        self.video_init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"

    def get_authorization_url(self, state: str) -> str:
        """Tao URL chuyen huong nguoi dung den trang dang nhap va cap quyen TikTok."""
        params = {
            "client_key": self.client_key,
            "scope": "user.info.basic,video.upload,video.publish",
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state
        }
        return f"{self.oauth_base_url}?{urllib.parse.urlencode(params)}"

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Doi ma authorization code lay access_token va refresh_token."""
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri
        }

        try:
            response = requests.post(self.token_url, headers=headers, data=data, timeout=30)
        except Exception as e:
            logger.warning(f"Loi ket noi khi exchange_code_for_token: {e}")
            raise TikTokApiException(f"Loi ket noi den TikTok API: {e}")

        if response.status_code == 401:
            raise TokenExpiredException("Authorization code khong hop le hoac da het han.")
        if response.status_code == 429:
            raise RateLimitException("Bi gioi han tan suat goi TikTok API (Rate Limit 429).")

        res_data = response.json()
        payload = res_data.get("data", res_data)

        if "error" in res_data and res_data.get("error"):
            err = res_data.get("error")
            err_code = err.get("code") if isinstance(err, dict) else err
            err_msg = err.get("message") if isinstance(err, dict) else res_data.get("error_description", "")
            if err_code != "ok" and err_code != 0 and err_code:
                logger.warning(f"TikTok token error: {err_code} - {err_msg}")
                raise TikTokApiException(f"TikTok API error: {err_code} - {err_msg}")

        if "access_token" not in payload:
            err_desc = res_data.get("error_description") or res_data.get("message") or "Khong lay duoc access_token"
            raise TikTokApiException(f"Loi lay token tu TikTok: {err_desc}")

        return {
            "access_token": payload.get("access_token"),
            "refresh_token": payload.get("refresh_token"),
            "open_id": payload.get("open_id"),
            "expires_in": int(payload.get("expires_in", 86400)),
            "refresh_expires_in": int(payload.get("refresh_expires_in", 31536000)),
            "scope": payload.get("scope", ""),
            "token_type": payload.get("token_type", "Bearer")
        }

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Lam moi access_token bang refresh_token hop le."""
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }

        try:
            response = requests.post(self.token_url, headers=headers, data=data, timeout=30)
        except Exception as e:
            logger.warning(f"Loi ket noi khi refresh_access_token: {e}")
            raise TikTokApiException(f"Loi ket noi den TikTok API: {e}")

        if response.status_code == 401:
            raise TokenExpiredException("Refresh token khong hop le hoac da het han.")
        if response.status_code == 429:
            raise RateLimitException("Bi gioi han tan suat goi TikTok API (Rate Limit 429).")

        res_data = response.json()
        payload = res_data.get("data", res_data)

        if "error" in res_data and res_data.get("error"):
            err = res_data.get("error")
            err_code = err.get("code") if isinstance(err, dict) else err
            err_msg = err.get("message") if isinstance(err, dict) else res_data.get("error_description", "")
            if err_code != "ok" and err_code != 0 and err_code:
                raise TikTokApiException(f"TikTok API error: {err_code} - {err_msg}")

        if "access_token" not in payload:
            err_desc = res_data.get("error_description") or res_data.get("message") or "Khong lam moi duoc access_token"
            raise TikTokApiException(f"Loi refresh token: {err_desc}")

        return {
            "access_token": payload.get("access_token"),
            "refresh_token": payload.get("refresh_token", refresh_token),
            "open_id": payload.get("open_id"),
            "expires_in": int(payload.get("expires_in", 86400)),
            "refresh_expires_in": int(payload.get("refresh_expires_in", 31536000)),
            "scope": payload.get("scope", ""),
            "token_type": payload.get("token_type", "Bearer")
        }

    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Lay thong tin co ban cua nguoi dung TikTok da cap quyen."""
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"{self.user_info_url}?fields=open_id,union_id,avatar_url,display_name"

        try:
            response = requests.get(url, headers=headers, timeout=30)
        except Exception as e:
            logger.warning(f"Loi ket noi khi get_user_info: {e}")
            raise TikTokApiException(f"Loi ket noi den TikTok API: {e}")

        if response.status_code == 401:
            raise TokenExpiredException("Access token da het han hoac bi thu hoi.")
        if response.status_code == 429:
            raise RateLimitException("Bi gioi han tan suat goi TikTok API (Rate Limit 429).")

        res_data = response.json()
        user_info = res_data.get("data", {}).get("user", {})
        if not user_info and "open_id" not in res_data:
            err = res_data.get("error", {})
            logger.warning(f"Khong lay duoc user info: {err}")
            raise TikTokApiException(f"Khong the lay thong tin user TikTok: {err.get('message', 'Unknown error')}")

        return user_info or res_data

    def validate_token(self, access_token: str) -> bool:
        """Kiem tra xem access_token con hoat dong hay khong."""
        try:
            info = self.get_user_info(access_token)
            return bool(info.get("open_id"))
        except TokenExpiredException:
            return False
        except Exception as e:
            logger.warning(f"Kiem tra token that bai: {e}")
            return False

    def init_video_upload(self, access_token: str, video_url: str) -> Dict[str, Any]:
        """POC: Khoi tao dang video bang co che PULL_FROM_URL (chua publish that)."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        body = {
            "post_info": {
                "title": "POC Upload Test",
                "privacy_level": "SELF_ONLY",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000
            },
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": video_url
            }
        }

        try:
            response = requests.post(self.video_init_url, headers=headers, json=body, timeout=30)
        except Exception as e:
            logger.warning(f"Loi ket noi khi init_video_upload: {e}")
            raise TikTokApiException(f"Loi ket noi den TikTok Content Posting API: {e}")

        if response.status_code == 401:
            raise TokenExpiredException("Access token khong hop le khi khoi tao video upload.")
        if response.status_code == 429:
            raise RateLimitException("Bi gioi han tan suat goi TikTok API (Rate Limit 429).")

        res_data = response.json()
        logger.info(f"TikTok POC upload init response: {res_data}")
        return res_data

