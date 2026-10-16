import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from notion_client import Client

logger = logging.getLogger(__name__)

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_TOKENS_DB_ID = os.getenv("NOTION_TOKENS_DB_ID")

if not NOTION_TOKEN or not NOTION_TOKENS_DB_ID:
    logger.warning("NOTION_TOKEN hoac NOTION_TOKENS_DB_ID chua duoc cau hinh trong moi truong!")

notion = Client(auth=NOTION_TOKEN) if NOTION_TOKEN else None

def _parse_token_page(page: Dict[str, Any]) -> Dict[str, Any]:
    """Chuyen doi ban ghi Notion token page thanh dictionary chuan."""
    props = page.get("properties", {})

    def get_title(name: str) -> str:
        arr = props.get(name, {}).get("title", [])
        return "".join([t.get("plain_text", "") for t in arr]) if arr else ""

    def get_rich_text(name: str) -> Optional[str]:
        arr = props.get(name, {}).get("rich_text", [])
        return "".join([t.get("plain_text", "") for t in arr]) if arr else None

    def get_date(name: str) -> Optional[str]:
        d = props.get(name, {}).get("date")
        return d.get("start") if d else None

    return {
        "open_id": get_title("open_id"),
        "access_token": get_rich_text("access_token"),
        "refresh_token": get_rich_text("refresh_token"),
        "expires_at": get_date("expires_at"),
        "refresh_expires_at": get_date("refresh_expires_at"),
        "scope": get_rich_text("scope")
    }

def save_token(
    open_id: str,
    access_token: str,
    refresh_token: str,
    expires_in: int,
    refresh_expires_in: int,
    scope: str
) -> str:
    """Luu hoac cap nhat token TikTok vao Notion tokens DB."""
    if not notion or not NOTION_TOKENS_DB_ID:
        raise Exception("Notion client chua khoi tao hoac thieu NOTION_TOKENS_DB_ID.")

    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(seconds=expires_in)).isoformat()
    refresh_expires_at = (now + timedelta(seconds=refresh_expires_in)).isoformat()
    updated_at = now.isoformat()

    properties = {
        "open_id": {"title": [{"text": {"content": open_id}}]},
        "access_token": {"rich_text": [{"text": {"content": access_token}}]},
        "refresh_token": {"rich_text": [{"text": {"content": refresh_token}}]},
        "expires_at": {"date": {"start": expires_at}},
        "refresh_expires_at": {"date": {"start": refresh_expires_at}},
        "scope": {"rich_text": [{"text": {"content": scope}}]},
        "updated_at": {"date": {"start": updated_at}}
    }

    response = notion.databases.query(
        database_id=NOTION_TOKENS_DB_ID,
        filter={
            "property": "open_id",
            "title": {"equals": open_id}
        }
    )
    results = response.get("results", [])

    if results:
        page_id = results[0]["id"]
        notion.pages.update(page_id=page_id, properties=properties)
        return page_id
    else:
        page = notion.pages.create(
            parent={"database_id": NOTION_TOKENS_DB_ID},
            properties=properties
        )
        return page["id"]

def get_token_by_open_id(open_id: str) -> Optional[Dict[str, Any]]:
    """Truy xuat thong tin token theo open_id tu Notion."""
    if not notion or not NOTION_TOKENS_DB_ID:
        raise Exception("Notion client chua khoi tao hoac thieu NOTION_TOKENS_DB_ID.")

    response = notion.databases.query(
        database_id=NOTION_TOKENS_DB_ID,
        filter={
            "property": "open_id",
            "title": {"equals": open_id}
        }
    )
    results = response.get("results", [])
    if not results:
        return None

    return _parse_token_page(results[0])

def update_token(
    open_id: str,
    access_token: str,
    refresh_token: str,
    expires_in: int,
    refresh_expires_in: int
) -> bool:
    """Cap nhat token moi sau khi refresh thanh cong."""
    if not notion or not NOTION_TOKENS_DB_ID:
        raise Exception("Notion client chua khoi tao hoac thieu NOTION_TOKENS_DB_ID.")

    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(seconds=expires_in)).isoformat()
    refresh_expires_at = (now + timedelta(seconds=refresh_expires_in)).isoformat()
    updated_at = now.isoformat()

    response = notion.databases.query(
        database_id=NOTION_TOKENS_DB_ID,
        filter={
            "property": "open_id",
            "title": {"equals": open_id}
        }
    )
    results = response.get("results", [])
    if not results:
        return False

    page_id = results[0]["id"]
    properties = {
        "access_token": {"rich_text": [{"text": {"content": access_token}}]},
        "refresh_token": {"rich_text": [{"text": {"content": refresh_token}}]},
        "expires_at": {"date": {"start": expires_at}},
        "refresh_expires_at": {"date": {"start": refresh_expires_at}},
        "updated_at": {"date": {"start": updated_at}}
    }
    notion.pages.update(page_id=page_id, properties=properties)
    return True

def get_latest_token() -> Optional[Dict[str, Any]]:
    """Lay ban ghi token moi nhat duoc luu trong he thong."""
    if not notion or not NOTION_TOKENS_DB_ID:
        raise Exception("Notion client chua khoi tao hoac thieu NOTION_TOKENS_DB_ID.")

    try:
        response = notion.databases.query(
            database_id=NOTION_TOKENS_DB_ID,
            sorts=[{"property": "updated_at", "direction": "descending"}],
            page_size=1
        )
    except Exception as e:
        logger.warning(f"Loi khi query sort updated_at trong tokens DB: {e}. Thu query khong sort...")
        response = notion.databases.query(
            database_id=NOTION_TOKENS_DB_ID,
            page_size=1
        )

    results = response.get("results", [])
    if not results:
        return None

    return _parse_token_page(results[0])

