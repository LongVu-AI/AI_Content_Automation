import os
import time
from datetime import datetime, timezone
from typing import Optional, List
import requests
from dotenv import load_dotenv
from app.logger import get_logger

load_dotenv()

logger = get_logger("notifier")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    logger.warning("Thieu TELEGRAM_BOT_TOKEN hoac TELEGRAM_CHAT_ID trong moi truong. Thong bao Telegram se khong hoat dong.")

# In-memory sliding window luu tru timestamp cac lan gui (Rate limit 5 tin / phut)
_sent_timestamps: List[float] = []

def reset_rate_limit() -> None:
    """Reset danh sach timestamp cho muc dich kiem thu."""
    global _sent_timestamps
    _sent_timestamps = []

def send_telegram_alert(
    message: str,
    severity: str = "ERROR",
    request_id: Optional[str] = None,
    component: Optional[str] = None,
    action: Optional[str] = None
) -> bool:
    """
    Gui thong bao canh bao ve Telegram group voi co che rate limit 5 tin/phut.
    """
    global _sent_timestamps

    now = time.time()
    # Xoa bo cac moc thoi gian qua 60 giay
    _sent_timestamps = [t for t in _sent_timestamps if now - t < 60.0]

    if len(_sent_timestamps) >= 5:
        logger.warning(
            "Telegram alert bi bo qua do vuot qua gioi han rate limit (toi da 5 tin/phut)",
            extra={"alert_message": message, "severity": severity, "request_id": request_id}
        )
        return False

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Khong the gui Telegram alert do chua cau hinh Token/Chat ID.")
        return False

    # Xac dinh hanh dong goi y
    if not action:
        msg_lower = message.lower()
        if "token" in msg_lower or "401" in msg_lower:
            action = "Kiem tra va refresh TikTok token trong Notion Tokens DB."
        elif "timeout" in msg_lower or "connection" in msg_lower:
            action = "Kiem tra lai ket noi mang va trang thai service ben ngoai."
        elif "notion" in msg_lower:
            action = "Kiem tra NOTION_TOKEN va schema cac cot trong Notion DB."
        else:
            action = "Kiem tra chi tiet stack trace trong /app/logs/app.log de xu ly."

    timestamp_iso = datetime.now(timezone.utc).isoformat()
    req_id_str = request_id if request_id else "N/A"
    comp_str = component if component else "Core Backend"

    text_content = (
        f"[{severity.upper()}] AI Content Automation Alert\n"
        f"Time: {timestamp_iso}\n"
        f"Request ID: {req_id_str}\n"
        f"Component: {comp_str}\n"
        f"Error: {message}\n"
        f"Suggested action: {action}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text_content
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200 and res.json().get("ok"):
            _sent_timestamps.append(now)
            logger.info(
                f"Da gui alert Telegram thanh cong: [{severity}] {message[:50]}...",
                extra={"request_id": request_id, "severity": severity}
            )
            return True
        else:
            logger.warning(
                f"Gui alert Telegram that bai voi ma {res.status_code}: {res.text}",
                extra={"status_code": res.status_code, "response": res.text}
            )
            return False
    except Exception as e:
        logger.warning(
            f"Ngoai le khi gui alert qua Telegram: {e}",
            extra={"error": str(e), "alert_message": message}
        )
        return False
