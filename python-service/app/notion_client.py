import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from notion_client import Client
from notion_client.errors import APIResponseError

from app.logger import get_logger

logger = get_logger("notion_client")

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

if not NOTION_TOKEN or not NOTION_DATABASE_ID:
    logger.warning("NOTION_TOKEN hoặc NOTION_DATABASE_ID chưa được cấu hình!")

notion = Client(auth=NOTION_TOKEN) if NOTION_TOKEN else None

def parse_notion_page(page: dict) -> dict:
    """
    Parse page object từ Notion DB thành dictionary chuẩn.
    
    Lưu ý: Nếu Notion Database thiếu các cột mới như 'locked_by' (Rich text)
    hoặc 'locked_at' (Date), người dùng cần thêm thủ công trên Notion:
    - locked_by: Rich text (Text) -- lưu execution_id của n8n
    - locked_at: Date -- lưu thời điểm khóa bản ghi
    """
    props = page.get("properties", {})
    
    def get_title(prop_name):
        if prop_name not in props:
            logger.warning(f"Thiếu cột {prop_name} trong Notion DB.")
        prop = props.get(prop_name, {})
        title_arr = prop.get("title", [])
        return "".join([t.get("plain_text", "") for t in title_arr]) if title_arr else ""

    def get_rich_text(prop_name):
        if prop_name not in props:
            logger.warning(f"Thiếu cột {prop_name} trong Notion DB.")
        prop = props.get(prop_name, {})
        rt_arr = prop.get("rich_text", [])
        return "".join([t.get("plain_text", "") for t in rt_arr]) if rt_arr else None

    def get_select(prop_name):
        if prop_name not in props:
            logger.warning(f"Thiếu cột {prop_name} trong Notion DB.")
        prop = props.get(prop_name, {})
        sel = prop.get("select")
        return sel.get("name") if sel else None

    def get_date(prop_name):
        if prop_name not in props:
            logger.warning(f"Thiếu cột {prop_name} trong Notion DB.")
        prop = props.get(prop_name, {})
        d = prop.get("date")
        return d.get("start") if d else None

    def get_url(prop_name):
        if prop_name not in props:
            logger.warning(f"Thiếu cột {prop_name} trong Notion DB.")
        prop = props.get(prop_name, {})
        return prop.get("url")

    def get_number(prop_name):
        if prop_name not in props:
            logger.warning(f"Thiếu cột {prop_name} trong Notion DB.")
        prop = props.get(prop_name, {})
        return prop.get("number")

    return {
        "request_id": get_title("request_id"),
        "product_name": get_rich_text("product_name"),
        "product_link": get_url("product_link"),
        "brand_name": get_rich_text("brand_name"),
        "hook_text": get_rich_text("hook_text"),
        "voice_over_text": get_rich_text("voice_over_text"),
        "text_on_screen": get_rich_text("text_on_screen"),
        "image_prompt_en": get_rich_text("image_prompt_en"),
        "bgm_vibe": get_rich_text("bgm_vibe"),
        "post_caption": get_rich_text("post_caption"),
        "hashtags": get_rich_text("hashtags"),
        "qc_score": get_number("qc_score"),
        "qc_feedback": get_rich_text("qc_feedback"),
        "video_url": get_rich_text("video_url") if props.get("video_url", {}).get("type") == "rich_text" else get_url("video_url"),
        "status": get_select("status"),
        "scheduled_at": get_date("scheduled_at"),
        "published_at": get_date("published_at"),
        "tiktok_publish_id": get_rich_text("tiktok_publish_id"),
        "retry_count": get_number("retry_count"),
        "last_error": get_rich_text("last_error"),
        "locked_by": get_rich_text("locked_by"),
        "locked_at": get_date("locked_at")
    }

def get_content_by_id(request_id: str) -> dict | None:
    if not notion or not NOTION_DATABASE_ID:
        raise Exception("Notion client chưa được khởi tạo (thiếu ENV).")
    
    response = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "property": "request_id",
            "title": {
                "equals": request_id
            }
        }
    )
    
    results = response.get("results", [])
    if not results:
        return None
        
    return parse_notion_page(results[0])

def list_contents(limit: int = 20, cursor: str | None = None) -> dict:
    if not notion or not NOTION_DATABASE_ID:
        raise Exception("Notion client chưa được khởi tạo (thiếu ENV).")
    
    query_args = {
        "database_id": NOTION_DATABASE_ID,
        "page_size": limit
    }
    if cursor:
        query_args["start_cursor"] = cursor
        
    response = notion.databases.query(**query_args)
    
    results = [parse_notion_page(page) for page in response.get("results", [])]
    
    return {
        "items": results,
        "next_cursor": response.get("next_cursor"),
        "has_more": response.get("has_more", False)
    }

def create_ai_output(payload) -> str:
    if not notion or not NOTION_DATABASE_ID:
        raise Exception("Notion client chưa được khởi tạo (thiếu ENV).")
        
    response = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "property": "request_id",
            "title": {
                "equals": payload.request_id
            }
        }
    )
    results = response.get("results", [])
    existing_page_id = results[0]["id"] if results else None
    
    properties = {
        "request_id": {"title": [{"text": {"content": payload.request_id}}]}
    }
    
    def to_rich_text(text: str):
        return {"rich_text": [{"text": {"content": text}}]} if text else {"rich_text": []}
        
    if payload.ai_result:
        res = payload.ai_result
        if res.hook_text is not None:
            properties["hook_text"] = to_rich_text(res.hook_text)
        if res.voice_over_text is not None:
            properties["voice_over_text"] = to_rich_text(res.voice_over_text)
        if res.text_on_screen is not None:
            properties["text_on_screen"] = to_rich_text(res.text_on_screen)
        if res.image_prompt_en is not None:
            properties["image_prompt_en"] = to_rich_text(res.image_prompt_en)
        if res.bgm_vibe is not None:
            properties["bgm_vibe"] = to_rich_text(res.bgm_vibe)
        if res.post_caption is not None:
            properties["post_caption"] = to_rich_text(res.post_caption)
        if res.hashtags is not None:
            hashtag_str = " ".join(res.hashtags)
            properties["hashtags"] = to_rich_text(hashtag_str)
        if res.qc_score is not None:
            properties["qc_score"] = {"number": res.qc_score}
        if res.qc_feedback is not None:
            properties["qc_feedback"] = to_rich_text(res.qc_feedback)
        if res.retry_count is not None:
            properties["retry_count"] = {"number": res.retry_count}
            
    if payload.status:
        status_val = "DRAFT" if payload.status.lower() == "success" else "FAILED"
        properties["status"] = {"select": {"name": status_val}}
        
    if existing_page_id:
        page = notion.pages.update(page_id=existing_page_id, properties=properties)
        return page["id"]
    else:
        page = notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties=properties
        )
        return page["id"]

def get_pending_reviews() -> list:
    if not notion or not NOTION_DATABASE_ID:
        raise Exception("Notion client chưa được khởi tạo (thiếu ENV).")
    
    response = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "property": "status",
            "select": {
                "equals": "PENDING_REVIEW"
            }
        }
    )
    return [parse_notion_page(page) for page in response.get("results", [])]

def update_status(request_id: str, status: str, reviewed_by: str | None = None, note: str | None = None) -> str | None:
    if not notion or not NOTION_DATABASE_ID:
        raise Exception("Notion client chưa được khởi tạo (thiếu ENV).")
        
    response = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "property": "request_id",
            "title": {
                "equals": request_id
            }
        }
    )
    results = response.get("results", [])
    if not results:
        return None
        
    existing_page_id = results[0]["id"]
    properties = {
        "status": {"select": {"name": status}}
    }
    
    if reviewed_by:
        note_text = note if note else ""
        msg = f"[REVIEWED by {reviewed_by}] {note_text}".strip()
        properties["last_error"] = {"rich_text": [{"text": {"content": msg}}]}
        
    page = notion.pages.update(page_id=existing_page_id, properties=properties)
    return page["id"]

def get_scheduled_due() -> list:
    """
    Query Notion DB với filter:
    - status = "APPROVED"
    - scheduled_at <= now
    - locked_by is empty
    Sort theo scheduled_at asc.
    Return list items.
    """
    if not notion or not NOTION_DATABASE_ID:
        raise Exception("Notion client chưa được khởi tạo (thiếu ENV).")
        
    now_str = datetime.now(timezone.utc).isoformat()
    try:
        response = notion.databases.query(
            database_id=NOTION_DATABASE_ID,
            filter={
                "and": [
                    {
                        "property": "status",
                        "select": {
                            "equals": "APPROVED"
                        }
                    },
                    {
                        "property": "scheduled_at",
                        "date": {
                            "on_or_before": now_str
                        }
                    },
                    {
                        "property": "locked_by",
                        "rich_text": {
                            "is_empty": True
                        }
                    }
                ]
            },
            sorts=[
                {
                    "property": "scheduled_at",
                    "direction": "ascending"
                }
            ]
        )
    except Exception as e:
        if "locked_by" in str(e) or "locked_at" in str(e) or "scheduled_at" in str(e):
            logger.error("Notion DB thiếu hoặc sai kiểu cột locked_by / locked_at / scheduled_at. Vui lòng kiểm tra lại cấu hình Notion DB.")
        raise e
        
    return [parse_notion_page(page) for page in response.get("results", [])]

def lock_and_publish(request_id: str, execution_id: str) -> dict:
    """
    Atomic logic:
    1. Query page theo request_id.
    2. Kiểm tra: nếu status != "APPROVED" hoặc locked_by không rỗng → return {locked: False, reason: "already_processed"}.
    3. Update page: status = "SCHEDULED", locked_by = execution_id, locked_at = now.
    4. Re-query page để verify locked_by = execution_id.
    5. Nếu verify OK → return {locked: True, page_id}.
    6. Nếu verify fail (race condition) → return {locked: False, reason: "race_lost"}.
    """
    if not notion or not NOTION_DATABASE_ID:
        raise Exception("Notion client chưa được khởi tạo (thiếu ENV).")
        
    response = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "property": "request_id",
            "title": {
                "equals": request_id
            }
        }
    )
    results = response.get("results", [])
    if not results:
        return {"locked": False, "reason": "content_not_found"}
        
    page = results[0]
    page_id = page["id"]
    current_data = parse_notion_page(page)
    
    if current_data.get("status") != "APPROVED" or current_data.get("locked_by"):
        return {"locked": False, "reason": "already_processed"}
        
    now_str = datetime.now(timezone.utc).isoformat()
    properties = {
        "status": {"select": {"name": "SCHEDULED"}},
        "locked_by": {"rich_text": [{"text": {"content": execution_id}}]},
        "locked_at": {"date": {"start": now_str}}
    }
    
    notion.pages.update(page_id=page_id, properties=properties)
    
    recheck_page = notion.pages.retrieve(page_id=page_id)
    recheck_data = parse_notion_page(recheck_page)
    
    if recheck_data.get("locked_by") == execution_id:
        return {"locked": True, "page_id": page_id}
    else:
        return {"locked": False, "reason": "race_lost"}

def update_status_publishing(request_id: str, execution_id: str) -> dict:
    """
    - Kiểm tra locked_by = execution_id trước khi update.
    - Update status = "PUBLISHING".
    - Return {success: True, page_id}.
    """
    if not notion or not NOTION_DATABASE_ID:
        raise Exception("Notion client chưa được khởi tạo (thiếu ENV).")
        
    response = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "property": "request_id",
            "title": {
                "equals": request_id
            }
        }
    )
    results = response.get("results", [])
    if not results:
        return {"success": False, "reason": "content_not_found"}
        
    page = results[0]
    page_id = page["id"]
    current_data = parse_notion_page(page)
    
    if current_data.get("locked_by") != execution_id:
        return {"success": False, "reason": "lock_mismatch_or_not_locked"}
        
    properties = {
        "status": {"select": {"name": "PUBLISHING"}}
    }
    notion.pages.update(page_id=page_id, properties=properties)
    return {"success": True, "page_id": page_id}

def update_publish_status(
    request_id: str,
    status: Optional[str] = None,
    tiktok_publish_id: Optional[str] = None,
    published_at: Optional[str] = None,
    last_error: Optional[str] = None,
    video_url: Optional[str] = None
) -> Optional[str]:
    """Cap nhat cac truong publish len Notion page theo request_id."""
    if not notion or not NOTION_DATABASE_ID:
        raise Exception("Notion client chua duoc khoi tao (thieu ENV).")

    response = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "property": "request_id",
            "title": {"equals": request_id}
        }
    )
    results = response.get("results", [])
    if not results:
        return None

    page_id = results[0]["id"]
    properties = {}
    if status:
        properties["status"] = {"select": {"name": status}}
    if tiktok_publish_id:
        properties["tiktok_publish_id"] = {"rich_text": [{"text": {"content": tiktok_publish_id}}]}
    if published_at:
        properties["published_at"] = {"date": {"start": published_at}}
    if last_error is not None:
        properties["last_error"] = {"rich_text": [{"text": {"content": last_error}}]}
    if video_url:
        properties["video_url"] = {"rich_text": [{"text": {"content": video_url}}]}

    if properties:
        notion.pages.update(page_id=page_id, properties=properties)
    return page_id

def get_content_by_publish_id(publish_id: str) -> Optional[Dict[str, Any]]:
    """Tim ban ghi trong Notion theo tiktok_publish_id."""
    if not notion or not NOTION_DATABASE_ID:
        raise Exception("Notion client chua duoc khoi tao (thieu ENV).")

    response = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "property": "tiktok_publish_id",
            "rich_text": {"equals": publish_id}
        }
    )
    results = response.get("results", [])
    if not results:
        return None
    return parse_notion_page(results[0])

def increment_retry_count(request_id: str) -> int:
    """Tang retry_count len 1 va luu vao Notion DB, tra ve gia tri moi."""
    if not notion or not NOTION_DATABASE_ID:
        raise Exception("Notion client chua duoc khoi tao (thieu ENV).")

    response = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "property": "request_id",
            "title": {"equals": request_id}
        }
    )
    results = response.get("results", [])
    if not results:
        raise ValueError(f"Khong tim thay content voi request_id: {request_id}")

    page = results[0]
    page_id = page["id"]
    current_props = page.get("properties", {})
    current_count = current_props.get("retry_count", {}).get("number") or 0
    new_count = int(current_count) + 1

    notion.pages.update(
        page_id=page_id,
        properties={
            "retry_count": {"number": new_count}
        }
    )
    return new_count

def log_error(request_id: str, error_message: str) -> None:
    """Ghi nhan loi vao cot last_error cua Notion page voi format [{timestamp}] {error_message}."""
    if not notion or not NOTION_DATABASE_ID:
        raise Exception("Notion client chua duoc khoi tao (thieu ENV).")

    response = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "property": "request_id",
            "title": {"equals": request_id}
        }
    )
    results = response.get("results", [])
    if not results:
        raise ValueError(f"Khong tim thay content voi request_id: {request_id}")

    page_id = results[0]["id"]
    timestamp_str = datetime.now(timezone.utc).isoformat()
    formatted_error = f"[{timestamp_str}] {error_message}"

    notion.pages.update(
        page_id=page_id,
        properties={
            "last_error": {"rich_text": [{"text": {"content": formatted_error}}]}
        }
    )

def get_failed_contents() -> list:
    """Lay danh sach cac video co status = FAILED va retry_count < 3."""
    if not notion or not NOTION_DATABASE_ID:
        raise Exception("Notion client chua duoc khoi tao (thieu ENV).")

    response = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "property": "status",
            "select": {"equals": "FAILED"}
        }
    )
    results = [parse_notion_page(p) for p in response.get("results", [])]
    filtered = [item for item in results if (item.get("retry_count") or 0) < 3]
    return filtered



