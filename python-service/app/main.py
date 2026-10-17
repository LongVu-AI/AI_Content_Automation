from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
from typing import Optional, Literal, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import secrets
import time
from dotenv import load_dotenv

load_dotenv()

from app import notion_client, token_storage
from app.logger import get_logger
from app.notifier import send_telegram_alert
from app.tiktok_client import (
    TikTokClient,
    TikTokApiException,
    TokenExpiredException,
    RateLimitException
)
from app.tiktok_publisher import TikTokPublisher

logger = get_logger("main")

tiktok_client = TikTokClient()
tiktok_publisher = TikTokPublisher(tiktok_client)
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

class PublishRequest(BaseModel):
    request_id: str
    video_url: Optional[str] = None
    video_path: Optional[str] = None
    title: Optional[str] = "AI TikTok Video"
    privacy_level: Optional[str] = "SELF_ONLY"

class PublishStatusRequest(BaseModel):
    request_id: str

class ApiResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[dict] = None
    meta: dict

# ===== Helpers =====
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def make_meta(req_id: Optional[str] = None) -> dict:
    return {
        "request_id": req_id or str(uuid.uuid4()),
        "timestamp": now_iso()
    }

# ===== Middleware & Exception Handlers =====
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.time()

    content_length = request.headers.get("content-length")
    body_size = int(content_length) if content_length and content_length.isdigit() else 0

    logger.info(
        f"Incoming request {request.method} {request.url.path}",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "body_size": body_size
        }
    )

    response = await call_next(request)

    duration_ms = round((time.time() - start_time) * 1000, 2)
    response.headers["X-Request-ID"] = request_id

    logger.info(
        f"Completed request {request.method} {request.url.path} with status {response.status_code} in {duration_ms}ms",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms
        }
    )
    return response

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    error_code = "NOT_FOUND" if exc.status_code == 404 else f"HTTP_{exc.status_code}"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": error_code,
                "message": exc.detail
            },
            "meta": make_meta(request_id)
        },
        headers={"X-Request-ID": request_id}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    logger.error(
        f"Unhandled error on {request.method} {request.url.path}: {exc}",
        extra={"request_id": request_id, "path": request.url.path, "error": str(exc)},
        exc_info=True
    )
    send_telegram_alert(
        message=f"Unhandled internal server error on {request.method} {request.url.path}: {exc}",
        severity="CRITICAL",
        request_id=request_id,
        component="FastAPI Global Exception Handler"
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error occurred."
            },
            "meta": make_meta(request_id)
        },
        headers={"X-Request-ID": request_id}
    )

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

@app.get("/api/v1/content/failed", response_model=ApiResponse)
def get_failed_content(request: Request):
    """Lay danh sach cac video co status = FAILED va retry_count < 3 de retry."""
    req_id = getattr(request.state, "request_id", None)
    try:
        data = notion_client.get_failed_contents()
        return {
            "success": True,
            "data": {"items": data, "count": len(data)},
            "error": None,
            "meta": make_meta(req_id)
        }
    except Exception as e:
        logger.error(f"Notion Failed Content Error: {e}")
        return {
            "success": False,
            "data": None,
            "error": {"code": "NOTION_API_ERROR", "message": str(e)},
            "meta": make_meta(req_id)
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

@app.post("/api/v1/tiktok/publish-from-url", response_model=ApiResponse)
def publish_from_url(payload: PublishRequest, request: Request):
    """Publish video TikTok bang phuong thuc PULL_FROM_URL kem retry tracking."""
    req_id = getattr(request.state, "request_id", None)
    content = None
    try:
        content = notion_client.get_content_by_id(payload.request_id)
        current_retry = (content.get("retry_count") or 0) if content else 0
        if current_retry >= 3:
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "MAX_RETRY_EXCEEDED",
                    "message": f"So lan thu lai da vuot qua gioi han cho phep (retry_count={current_retry})."
                },
                "meta": make_meta(req_id)
            }

        video_url = payload.video_url
        if not video_url:
            if content and content.get("video_url"):
                video_url = content.get("video_url")
            else:
                return {
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "MISSING_VIDEO_URL",
                        "message": "video_url la bat buoc (khong tim thay trong request hoac Notion)."
                    },
                    "meta": make_meta(req_id)
                }

        result = tiktok_publisher.publish_from_url(
            request_id=payload.request_id,
            video_url=video_url,
            title=payload.title or "AI TikTok Video",
            privacy_level=payload.privacy_level or "SELF_ONLY"
        )
        return {
            "success": True,
            "data": result,
            "error": None,
            "meta": make_meta(req_id)
        }
    except Exception as e:
        logger.error(f"Loi publish_from_url: {e}", extra={"request_id": payload.request_id})
        new_retry = 1
        try:
            new_retry = notion_client.increment_retry_count(payload.request_id)
            notion_client.log_error(payload.request_id, f"Publish URL that bai: {e}")
        except Exception as log_err:
            logger.warning(f"Khong the cap nhat retry_count: {log_err}")

        if new_retry >= 3:
            try:
                notion_client.update_publish_status(payload.request_id, status="FAILED", last_error=str(e))
            except Exception:
                pass
            send_telegram_alert(
                message=f"Publish from URL that bai vuot qua 3 lan cho request {payload.request_id}: {e}",
                severity="ERROR",
                request_id=payload.request_id,
                component="TikTok Publisher (URL)"
            )

        return {
            "success": False,
            "data": None,
            "error": {"code": "PUBLISH_FROM_URL_FAILED", "message": str(e)},
            "meta": make_meta(req_id)
        }

@app.post("/api/v1/tiktok/publish-from-file", response_model=ApiResponse)
def publish_from_file(payload: PublishRequest, request: Request):
    """Publish video TikTok bang phuong thuc FILE_UPLOAD chia chunk kem retry tracking."""
    req_id = getattr(request.state, "request_id", None)
    try:
        content = notion_client.get_content_by_id(payload.request_id)
        current_retry = (content.get("retry_count") or 0) if content else 0
        if current_retry >= 3:
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "MAX_RETRY_EXCEEDED",
                    "message": f"So lan thu lai da vuot qua gioi han cho phep (retry_count={current_retry})."
                },
                "meta": make_meta(req_id)
            }

        if not payload.video_path:
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "MISSING_VIDEO_PATH",
                    "message": "video_path la bat buoc."
                },
                "meta": make_meta(req_id)
            }

        result = tiktok_publisher.publish_from_file(
            request_id=payload.request_id,
            video_path=payload.video_path,
            title=payload.title or "AI TikTok Video",
            privacy_level=payload.privacy_level or "SELF_ONLY"
        )
        return {
            "success": True,
            "data": result,
            "error": None,
            "meta": make_meta(req_id)
        }
    except Exception as e:
        logger.error(f"Loi publish_from_file: {e}", extra={"request_id": payload.request_id})
        new_retry = 1
        try:
            new_retry = notion_client.increment_retry_count(payload.request_id)
            notion_client.log_error(payload.request_id, f"Publish file that bai: {e}")
        except Exception as log_err:
            logger.warning(f"Khong the cap nhat retry_count: {log_err}")

        if new_retry >= 3:
            try:
                notion_client.update_publish_status(payload.request_id, status="FAILED", last_error=str(e))
            except Exception:
                pass
            send_telegram_alert(
                message=f"Publish from file that bai vuot qua 3 lan cho request {payload.request_id}: {e}",
                severity="ERROR",
                request_id=payload.request_id,
                component="TikTok Publisher (File)"
            )

        return {
            "success": False,
            "data": None,
            "error": {"code": "PUBLISH_FROM_FILE_FAILED", "message": str(e)},
            "meta": make_meta(req_id)
        }

@app.post("/api/v1/tiktok/check-status", response_model=ApiResponse)
def check_publish_status(payload: PublishStatusRequest):
    """Kiem tra trang thai video publish tren TikTok va dong bo ve Notion."""
    try:
        result = tiktok_publisher.check_and_update_status(payload.request_id)
        return {
            "success": True,
            "data": result,
            "error": None,
            "meta": make_meta()
        }
    except Exception as e:
        logger.error(f"Loi check_publish_status: {e}")
        return {
            "success": False,
            "data": None,
            "error": {"code": "CHECK_STATUS_FAILED", "message": str(e)},
            "meta": make_meta()
        }

@app.post("/api/v1/tiktok/webhook")
def tiktok_webhook(event_payload: Dict[str, Any]):
    """Webhook nhan callback su kien publish video tu TikTok."""
    try:
        logger.info(f"Nhan TikTok webhook: {event_payload}")
        publish_id = (
            event_payload.get("publish_id")
            or event_payload.get("data", {}).get("publish_id")
            or (event_payload.get("entry", [{}])[0].get("publish_id") if isinstance(event_payload.get("entry"), list) and event_payload.get("entry") else None)
        )
        if publish_id:
            content = notion_client.get_content_by_publish_id(publish_id)
            if content and content.get("request_id"):
                tiktok_publisher.check_and_update_status(content["request_id"])
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Loi xu ly TikTok webhook: {e}")
        return {"status": "ok"}