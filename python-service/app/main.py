from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime, timezone
import uuid
import logging
from dotenv import load_dotenv

load_dotenv()

from app import notion_client

logger = logging.getLogger(__name__)

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
    status: Literal["APPROVED", "NEEDS_REVISION", "PUBLISHING", "PUBLISHED", "FAILED", "SCHEDULED"]
    reviewed_by: Optional[str] = None
    note: Optional[str] = None

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