import os
import sys
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from typing import Optional, Dict, Any

class JsonFormatter(logging.Formatter):
    """Formatter dinh dang log theo chuan JSON cho production."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }

        # Lay request_id neu duoc gan vao log record
        request_id = getattr(record, "request_id", None)
        if request_id:
            log_data["request_id"] = str(request_id)

        # Trich xuat cac truong extra neu co
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "request_id", "message"
        }
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith("_")
        }
        if extra_fields:
            log_data["extra"] = extra_fields

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)

_configured = False

def setup_logging() -> None:
    """Cau hinh logging he thong gom ConsoleHandler va RotatingFileHandler."""
    global _configured
    if _configured:
        return

    # Thu muc log ho tro ca trong container va moi truong local
    log_dir = os.getenv("LOG_DIR", "/app/logs" if os.path.exists("/app") else "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "app.log")
    except Exception as e:
        sys.stderr.write(f"Khong the tao thu muc log {log_dir}: {e}\n")
        log_file = "app.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # 1. Console Handler (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(console_handler)

    # 2. Rotating File Handler (DEBUG level, max 10MB, keep 5 files)
    try:
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JsonFormatter())
        root_logger.addHandler(file_handler)
    except Exception as e:
        sys.stderr.write(f"Khong the khoi tao RotatingFileHandler: {e}\n")

    _configured = True

def get_logger(name: str) -> logging.Logger:
    """Lay doi tuong Logger da duoc cau hinh format JSON."""
    if not _configured:
        setup_logging()
    return logging.getLogger(name)

