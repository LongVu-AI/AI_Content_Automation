import os
import logging
from notion_client import Client
from notion_client.errors import APIResponseError

logger = logging.getLogger(__name__)

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

if not NOTION_TOKEN or not NOTION_DATABASE_ID:
    logger.warning("NOTION_TOKEN hoặc NOTION_DATABASE_ID chưa được cấu hình!")

notion = Client(auth=NOTION_TOKEN) if NOTION_TOKEN else None

def parse_notion_page(page: dict) -> dict:
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
        "video_url": get_url("video_url"),
        "status": get_select("status"),
        "scheduled_at": get_date("scheduled_at"),
        "published_at": get_date("published_at"),
        "tiktok_publish_id": get_rich_text("tiktok_publish_id"),
        "retry_count": get_number("retry_count"),
        "last_error": get_rich_text("last_error")
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
