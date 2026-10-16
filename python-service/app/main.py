from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional, Literal, Dict
from datetime import datetime, timezone, timedelta
import uuid
import logging
import secrets
import time
from dotenv import load_dotenv

load_dotenv()

from app import notion_client, token_storage
from app.tiktok_client import (
    TikTokClient,
    TikTokApiException,
    TokenExpiredException,
    RateLimitException
)

logger = logging.getLogger(__name__)

tiktok_client = TikTokClient()
oauth_states: Dict[str, float] = {}

app = FastAPI(
    title="AI Content Automation API",
    version="0.2.0",
    description="Microservice cho hệ thống AI Content & TikTok Automation"
)

# ===== Models =====
class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: str

class ContentIntakeRequest(BaseModel):
    request_id: str
    product_name: str
    product_link: Optional[str] = None
    brand_name: Optional[str] = None
    hook_text: Optional[str] = None
    voice_over_text: Optional[str] = None
    text_on_screen: Optional[str] = None
    image_prompt_en: Optional[str] = None
    bgm_vibe: Optional[str] = None
    post_caption: Optional[str] = None
    hashtags: Optional[str] = None
    qc_score: Optional[float] = None
    qc_feedback: Optional[str] = None
    video_url: Optional[str] = None

class AIResult(BaseModel):
    hook_text: Optional[str] = None
    voice_over_text: Optional[str] = None
    text_on_screen: Optional[str] = None
    image_prompt_en: Optional[str] = None
    bgm_vibe: Optional[str] = None
    post_caption: Optional[str] = None
    hashtags: Optional[list[str]] = None
    qc_score: Optional[float] = None
    qc_feedback: Optional[str] = None
    retry_count: Optional[int] = None

class AIMetadata(BaseModel):
    processing_time_seconds: Optional[int] = None
    model_used: Optional[str] = None
    created_at: Optional[str] = None

class AIOutputRequest(BaseModel):
    request_id: str
    status: str
    ai_result: Optional[AIResult] = None
    metadata: Optional[AIMetadata] = None
    error: Optional[dict] = None

class StatusUpdateRequest(BaseModel):
    status: Literal["PENDING_REVIEW", "APPROVED", "NEEDS_REVISION", "PUBLISHING", "PUBLISHED", "FAILED", "SCHEDULED"]
    reviewed_by: Optional[str] = None
    note: Optional[str] = None

class ExecutionRequest(BaseModel):
    execution_id: str

class TokenInfo(BaseModel):
    open_id: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    scope: Optional[str] = None
    expires_at: Optional[str] = None

class POCUploadRequest(BaseModel):
    video_url: str

class ApiResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[dict] = None
    meta: dict

# ===== Helpers =====
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def make_meta() -> dict:
    return {
        "request_id": str(uuid.uuid4()),
        "timestamp": now_iso()
    }

# ===== Endpoints =====
@app.get("/health", response_model=HealthResponse)
def health():
    return {
        "status": "ok",
        "service": "python-fastapi",
        "version": "0.2.0",
        "timestamp": now_iso()
    }

@app.post("/api/v1/content/intake", response_model=ApiResponse)
def content_intake(payload: ContentIntakeRequest):
    if not payload.request_id or not payload.product_name:
        raise HTTPException(status_code=400, detail="request_id and product_name are required")

    return {
        "success": True,
        "data": {
            "request_id": payload.request_id,
            "product_name": payload.product_name,
            "status": "received",
            "message": "Content Intake đã được tiếp nhận."
        },
        "error": None,
        "meta": make_meta()
    }

@app.get("/api/v1/content/pending-review", response_model=ApiResponse)
def list_pending_reviews():
    try:
        data = notion_client.get_pending_reviews()
        return {
            "success": True,
            "data": {"items": data},
            "error": None,
            "meta": make_meta()
        }
    except Exception as e:
        logger.error(f"Notion API Error: {e}")
        return {
            "success": False,
            "data": None,
            "error": {"code": "NOTION_API_ERROR", "message": str(e)},
            "meta": make_meta()
        }

@app.get("/api/v1/content/scheduled-due", response_model=ApiResponse)
def get_scheduled_due():
    try:
        data = notion_client.get_scheduled_due()
        return {
            "success": True,
            "data": {"items": data},
            "error": None,
            "meta": make_meta()
        }
    except Exception as e:
        logger.error(f"Notion Scheduled Due Error: {e}")
        return {
            "success": False,
            "data": None,
            "error": {"code": "NOTION_API_ERROR", "message": str(e)},
            "meta": make_meta()
        }

@app.get("/api/v1/content/{request_id}", response_model=ApiResponse)
def get_content(request_id: str):
    try:
        data = notion_client.get_content_by_id(request_id)
        if not data:
            return {
                "success": False,
                "data": None,
                "error": {"code": "CONTENT_NOT_FOUND", "message": "Không tìm thấy request_id trong Notion"},
                "meta": make_meta()
            }
        return {
            "success": True,
            "data": data,
            "error": None,
            "meta": make_meta()
        }
    except Exception as e:
        logger.error(f"Notion API Error: {e}")
        return {
            "success": False,
            "data": None,
            "error": {"code": "NOTION_API_ERROR", "message": str(e)},
            "meta": make_meta()
        }

@app.get("/api/v1/content", response_model=ApiResponse)
def list_content(limit: int = Query(20, ge=1, le=100), cursor: Optional[str] = None):
    try:
        data = notion_client.list_contents(limit=limit, cursor=cursor)
        return {
            "success": True,
            "data": data,
            "error": None,
            "meta": make_meta()
        }
    except Exception as e:
        logger.error(f"Notion API Error: {e}")
        return {
            "success": False,
            "data": None,
            "error": {"code": "NOTION_API_ERROR", "message": str(e)},
            "meta": make_meta()
        }

@app.post("/api/v1/content/ai-output", response_model=ApiResponse)
def content_ai_output(payload: AIOutputRequest):
    if not payload.request_id:
        raise HTTPException(status_code=400, detail="request_id is required")

    try:
        notion_page_id = notion_client.create_ai_output(payload)
        return {
            "success": True,
            "data": {
                "request_id": payload.request_id,
                "notion_page_id": notion_page_id
            },
            "error": None,
            "meta": make_meta()
        }
    except Exception as e:
        logger.error(f"Lỗi khi lưu AI Output lên Notion: {e}")
        return {
            "success": False,
            "data": None,
            "error": {"code": "NOTION_UPDATE_ERROR", "message": str(e)},
            "meta": make_meta()
        }

@app.patch("/api/v1/content/{request_id}/status", response_model=ApiResponse)
def update_content_status(request_id: str, payload: StatusUpdateRequest):
    try:
        page_id = notion_client.update_status(
            request_id, payload.status, payload.reviewed_by, payload.note
        )
        if not page_id:
            return {
                "success": False,
                "data": None,
                "error": {"code": "CONTENT_NOT_FOUND", "message": "Không tìm thấy request_id trong Notion"},
                "meta": make_meta()
            }
        return {
            "success": True,
            "data": {
                "request_id": request_id,
                "status": payload.status,
                "updated_at": now_iso()
            },
            "error": None,
            "meta": make_meta()
        }
    except Exception as e:
        logger.error(f"Notion Update Error: {e}")
        return {
            "success": False,
            "data": None,
            "error": {"code": "NOTION_UPDATE_ERROR", "message": str(e)},
            "meta": make_meta()
        }

@app.post("/api/v1/content/{request_id}/lock", response_model=ApiResponse)
def lock_content(request_id: str, payload: ExecutionRequest):
    if not payload.execution_id:
        raise HTTPException(status_code=400, detail="execution_id is required")
    try:
        result = notion_client.lock_and_publish(request_id, payload.execution_id)
        if result.get("locked"):
            return {
                "success": True,
                "data": result,
                "error": None,
                "meta": make_meta()
            }
        else:
            return {
                "success": False,
                "data": result,
                "error": {
                    "code": "LOCK_FAILED",
                    "message": f"Lock failed: {result.get('reason')}"
                },
                "meta": make_meta()
            }
    except Exception as e:
        logger.error(f"Lock Content Error: {e}")
        return {
            "success": False,
            "data": None,
            "error": {"code": "NOTION_UPDATE_ERROR", "message": str(e)},
            "meta": make_meta()
        }

@app.post("/api/v1/content/{request_id}/publish", response_model=ApiResponse)
def publish_content(request_id: str, payload: ExecutionRequest):
    if not payload.execution_id:
        raise HTTPException(status_code=400, detail="execution_id is required")
    try:
        result = notion_client.update_status_publishing(request_id, payload.execution_id)
        if result.get("success"):
            return {
                "success": True,
                "data": result,
                "error": None,
                "meta": make_meta()
            }
        else:
            return {
                "success": False,
                "data": result,
                "error": {
                    "code": "PUBLISH_FAILED",
                    "message": f"Publish failed: {result.get('reason')}"
                },
                "meta": make_meta()
            }
    except Exception as e:
        logger.error(f"Publish Content Error: {e}")
        return {
            "success": False,
            "data": None,
            "error": {"code": "NOTION_UPDATE_ERROR", "message": str(e)},
            "meta": make_meta()
        }

# ===== TikTok OAuth & POC Endpoints =====

@app.get("/api/v1/tiktok/auth")
def tiktok_auth():
    """Chuyen huong nguoi dung den trang dang nhap TikTok OAuth."""
    now = time.time()
    for s, t in list(oauth_states.items()):
        if now - t > 600:
            oauth_states.pop(s, None)

    state = secrets.token_urlsafe(16)
    oauth_states[state] = now
    url = tiktok_client.get_authorization_url(state)
    return RedirectResponse(url=url)

@app.get("/api/v1/tiktok/callback", response_class=HTMLResponse)
def tiktok_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """Tiep nhan callback tu TikTok OAuth sau khi nguoi dung cap quyen."""
    if error:
        raise HTTPException(status_code=400, detail=f"TikTok OAuth error: {error}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Thieu ma code hoac state trong callback URL.")

    stored_time = oauth_states.pop(state, None)
    if not stored_time or (time.time() - stored_time > 600):
        raise HTTPException(status_code=400, detail="State khong hop le hoac da het han.")

    try:
        token_data = tiktok_client.exchange_code_for_token(code)
        open_id = token_data["open_id"]

        token_storage.save_token(
            open_id=open_id,
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in=token_data["expires_in"],
            refresh_expires_in=token_data["refresh_expires_in"],
            scope=token_data.get("scope", "")
        )

        user_info = {}
        try:
            user_info = tiktok_client.get_user_info(token_data["access_token"])
        except Exception as e:
            logger.warning(f"Chua the lay user info ngay sau khi cap token: {e}")

        display_name = user_info.get("display_name", "TikTok User")

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Xac thuc TikTok thanh cong</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; text-align: center; padding: 60px 20px; background-color: #f8f9fa; color: #333; }}
                .card {{ background: white; max-width: 500px; margin: 0 auto; padding: 40px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
                h2 {{ color: #0070f3; margin-bottom: 20px; }}
                p {{ font-size: 16px; margin: 8px 0; }}
                .highlight {{ font-weight: bold; color: #111; }}
                .note {{ margin-top: 24px; font-size: 14px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2>Xac thuc TikTok thanh cong!</h2>
                <p>Nguoi dung: <span class="highlight">{display_name}</span></p>
                <p>Open ID: <span class="highlight">{open_id}</span></p>
                <p class="note">He thong da luu tru token an toan vao Notion Database. Ban co the dong tab nay va quay lai ung dung.</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

    except TikTokApiException as e:
        logger.error(f"Loi TikTok OAuth Callback: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Loi xu ly callback: {e}")
        raise HTTPException(status_code=500, detail=f"Loi he thong khi luu token: {e}")

@app.get("/api/v1/tiktok/status", response_model=ApiResponse)
def get_tiktok_status():
    """Kiem tra trang thai ket noi va tinh hop le cua token TikTok."""
    try:
        token_info = token_storage.get_latest_token()
        if not token_info or not token_info.get("access_token"):
            return {
                "success": True,
                "data": {"connected": False},
                "error": None,
                "meta": make_meta()
            }

        access_token = token_info.get("access_token")
        is_valid = tiktok_client.validate_token(access_token)

        if is_valid:
            user_info = {}
            try:
                user_info = tiktok_client.get_user_info(access_token)
            except Exception:
                pass

            return {
                "success": True,
                "data": {
                    "connected": True,
                    "open_id": token_info.get("open_id"),
                    "expires_at": token_info.get("expires_at"),
                    "display_name": user_info.get("display_name", "")
                },
                "error": None,
                "meta": make_meta()
            }

        refresh_token = token_info.get("refresh_token")
        if refresh_token:
            try:
                new_token = tiktok_client.refresh_access_token(refresh_token)
                token_storage.update_token(
                    open_id=new_token["open_id"],
                    access_token=new_token["access_token"],
                    refresh_token=new_token["refresh_token"],
                    expires_in=new_token["expires_in"],
                    refresh_expires_in=new_token["refresh_expires_in"]
                )
                now_utc = datetime.now(timezone.utc)
                new_expires_at = (now_utc + timedelta(seconds=new_token["expires_in"])).isoformat()
                return {
                    "success": True,
                    "data": {
                        "connected": True,
                        "open_id": new_token["open_id"],
                        "expires_at": new_expires_at,
                        "display_name": "Refreshed"
                    },
                    "error": None,
                    "meta": make_meta()
                }
            except Exception as e:
                logger.warning(f"Tu dong refresh that bai: {e}")

        return {
            "success": True,
            "data": {
                "connected": False,
                "open_id": token_info.get("open_id"),
                "reason": "token_expired_and_refresh_failed"
            },
            "error": None,
            "meta": make_meta()
        }

    except Exception as e:
        logger.error(f"Loi kiem tra status TikTok: {e}")
        return {
            "success": False,
            "data": None,
            "error": {"code": "TIKTOK_STATUS_ERROR", "message": str(e)},
            "meta": make_meta()
        }

@app.post("/api/v1/tiktok/refresh", response_model=ApiResponse)
def refresh_tiktok_token():
    """Chu dong lam moi access_token bang refresh_token moi nhat."""
    try:
        token_info = token_storage.get_latest_token()
        if not token_info or not token_info.get("refresh_token"):
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "REFRESH_TOKEN_NOT_FOUND",
                    "message": "Khong tim thay refresh token trong database."
                },
                "meta": make_meta()
            }

        new_token = tiktok_client.refresh_access_token(token_info["refresh_token"])
        token_storage.update_token(
            open_id=new_token["open_id"],
            access_token=new_token["access_token"],
            refresh_token=new_token["refresh_token"],
            expires_in=new_token["expires_in"],
            refresh_expires_in=new_token["refresh_expires_in"]
        )

        return {
            "success": True,
            "data": {
                "open_id": new_token["open_id"],
                "expires_in": new_token["expires_in"],
                "token_type": new_token.get("token_type", "Bearer")
            },
            "error": None,
            "meta": make_meta()
        }
    except Exception as e:
        logger.error(f"Loi khi refresh TikTok token: {e}")
        return {
            "success": False,
            "data": None,
            "error": {"code": "REFRESH_FAILED", "message": str(e)},
            "meta": make_meta()
        }

@app.post("/api/v1/tiktok/poc-upload", response_model=ApiResponse)
def poc_upload_video(payload: POCUploadRequest):
    """POC: Goi khoi tao video upload toi TikTok Content Posting API (PULL_FROM_URL)."""
    if not payload.video_url:
        raise HTTPException(status_code=400, detail="video_url is required")

    try:
        token_info = token_storage.get_latest_token()
        if not token_info or not token_info.get("access_token"):
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "NOT_AUTHENTICATED",
                    "message": "Chua co token TikTok hop le. Vui long OAuth truoc."
                },
                "meta": make_meta()
            }

        result = tiktok_client.init_video_upload(
            access_token=token_info["access_token"],
            video_url=payload.video_url
        )

        return {
            "success": True,
            "data": result,
            "error": None,
            "meta": make_meta()
        }
    except Exception as e:
        logger.error(f"Loi khoi tao video upload: {e}")
        return {
            "success": False,
            "data": None,
            "error": {"code": "POC_UPLOAD_ERROR", "message": str(e)},
            "meta": make_meta()
        }