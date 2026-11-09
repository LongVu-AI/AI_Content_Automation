"""Durable v2 receipts + resumable Notion content sections. Legacy endpoints are unchanged."""
import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.contracts_v2 import HandoffV2
from app import notion_client as nc

router = APIRouter(prefix="/api/v2/content", tags=["Content Studio v2"])
_lock = threading.RLock()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def database_id():
    """Only v2 uses the optional acceptance database; v1 keeps its own config."""
    return (os.getenv("NOTION_V2_DATABASE_ID") or nc.NOTION_DATABASE_ID or "").strip()


def same_database(left, right):
    return str(left or "").replace("-", "").lower() == str(right or "").replace("-", "").lower()


def folder():
    p = Path(os.getenv("HANDOFF_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data")))
    p.mkdir(parents=True, exist_ok=True)
    return p


def connect():
    db = sqlite3.connect(folder() / "handoffs.sqlite3", timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS receipts(request_id TEXT,revision INTEGER,digest TEXT,
      status TEXT,page_id TEXT,section_id TEXT,block_cursor INTEGER DEFAULT 0,error TEXT,
      PRIMARY KEY(request_id,revision))""")
    if "database_id" not in {r[1] for r in db.execute("PRAGMA table_info(receipts)")}:
        db.execute("ALTER TABLE receipts ADD COLUMN database_id TEXT")
    db.commit()
    return db


def patch_receipt(db, req, rev, **fields):
    keys = list(fields)
    db.execute("UPDATE receipts SET " + ",".join(k + "=?" for k in keys) + " WHERE request_id=? AND revision=?",
               [fields[k] for k in keys] + [req, rev])
    db.commit()


def rich(text):
    # Each Notion rich-text object is bounded; never truncate a prompt.
    return [{"type": "text", "text": {"content": text[i:i + 1700]}} for i in range(0, len(text), 1700)]


def paragraph(text):
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich(text)}}


def blocks_for(bundle):
    result = [paragraph("Sản phẩm: " + bundle.product.name), paragraph("Nhân vật: " + bundle.character.name)]
    for s in bundle.scenes:
        result.append(paragraph(f"CẢNH {s.id} · {s.part} · 8 giây"))
        # Separate blocks avoid rich-text array limits for long prompts.
        for i in range(0, len(s.prompt_en), 1700):
            result.append({"object": "block", "type": "code", "code": {"language": "plain text", "rich_text": rich(s.prompt_en[i:i+1700])}})
        result += [paragraph("Lời thoại / thuyết minh: " + s.dialogue_vi), paragraph("Chữ khi dựng: " + s.overlay_text)]
    p = bundle.publishing
    result += [paragraph("CAPTION\n" + "\n\n".join(p.captions)), paragraph("HASHTAG\n" + " ".join(p.hashtags)),
               paragraph("BÌNH LUẬN GHIM\n" + p.pinned_comment), paragraph("SLOGAN\n" + "\n".join(p.slogans)),
               paragraph("Đây là bộ prompt đã chốt; video chưa được duyệt để đăng.")]
    return result


def list_children(block_id):
    rows, cursor = [], None
    while True:
        args = {"block_id": block_id, "page_size": 100}
        if cursor:
            args["start_cursor"] = cursor
        response = nc.notion.blocks.children.list(**args)
        rows.extend(response.get("results", []))
        if not response.get("has_more"):
            return rows
        cursor = response["next_cursor"]


def existing_page(request_id):
    response = nc.notion.databases.query(database_id=database_id(),
        filter={"property": "request_id", "title": {"equals": request_id}})
    return next(iter(response.get("results", [])), None)


def save_to_notion(bundle, db, receipt):
    if not nc.notion or not database_id():
        raise RuntimeError("Chưa cấu hình Notion cho Automation.")
    # Always check current remote state, including when retrying a partial write.
    page = existing_page(bundle.request_id)
    if page:
        status_prop = page.get("properties", {}).get("status", {})
        status = (status_prop.get("select") or status_prop.get("status") or {}).get("name")
        if status not in (None, "DRAFT", "FAILED"):
            raise HTTPException(409, "Nội dung đã sang duyệt video/lập lịch/đăng. Hãy tạo bản mới.")
    p = bundle.publishing
    properties = {
        "request_id": {"title": rich(bundle.request_id)},
        "product_name": {"rich_text": rich(bundle.product.name)},
        "product_link": {"url": bundle.product.product_link},
        "hook_text": {"rich_text": rich(bundle.scenes[0].dialogue_vi)},
        "voice_over_text": {"rich_text": rich("\n".join(s.dialogue_vi for s in bundle.scenes))},
        "text_on_screen": {"rich_text": rich("\n".join(s.overlay_text for s in bundle.scenes if s.overlay_text))},
        "image_prompt_en": {"rich_text": rich("Prompt từng cảnh nằm trong phần Content Studio v2 bên dưới.")},
        "post_caption": {"rich_text": rich(p.captions[p.selected_caption])},
        "hashtags": {"rich_text": rich(" ".join(p.hashtags))},
        "qc_score": {"number": bundle.qc.qc_score},
        "qc_feedback": {"rich_text": rich(bundle.qc.feedback)},
        "status": {"select": {"name": "DRAFT"}},
    }
    if page:
        page_id = page["id"]
        nc.notion.pages.update(page_id=page_id, properties=properties)
    else:
        page_id = nc.notion.pages.create(parent={"database_id": database_id()}, properties=properties)["id"]
    patch_receipt(db, bundle.request_id, bundle.revision, page_id=page_id)
    marker = f"Content Studio v2 | {bundle.request_id} | r{bundle.revision} | {receipt['digest']}"
    sections = list_children(page_id)
    section = next((b for b in sections if b.get("type") == "toggle" and
                    "".join(t.get("plain_text", t.get("text", {}).get("content", "")) for t in b["toggle"].get("rich_text", [])) == marker), None)
    if section:
        section_id = section["id"]
    else:
        section_id = nc.notion.blocks.children.append(block_id=page_id, children=[
            {"object": "block", "type": "toggle", "toggle": {"rich_text": rich(marker)}}])["results"][0]["id"]
    patch_receipt(db, bundle.request_id, bundle.revision, section_id=section_id)
    expected = blocks_for(bundle)
    # Reading actual children also recovers an append that succeeded before a local crash.
    actual = list_children(section_id)
    for i, child in enumerate(actual):
        if i >= len(expected):
            raise RuntimeError("Phần Notion có nội dung ngoài gói đã ghi. Cần kiểm tra thủ công.")
        kind = expected[i]["type"]
        actual_text = "".join(t.get("plain_text", t.get("text", {}).get("content", "")) for t in child.get(kind, {}).get("rich_text", []))
        wanted = "".join(t["text"]["content"] for t in expected[i][kind]["rich_text"])
        if child.get("type") != kind or actual_text != wanted:
            raise RuntimeError("Nội dung Notion đã được chỉnh trực tiếp. Không ghi đè tự động.")
    for start in range(len(actual), len(expected), 30):
        batch = expected[start:start+30]
        nc.notion.blocks.children.append(block_id=section_id, children=batch)
        patch_receipt(db, bundle.request_id, bundle.revision, block_cursor=start + len(batch))
    return page_id


@router.post("/ai-output")
def receive(bundle: HandoffV2):
    raw = bundle.model_dump()
    digest = hashlib.sha256(canonical(raw).encode("utf-8")).hexdigest()
    with _lock:
        target = database_id()
        if not target or not nc.notion:
            raise HTTPException(503, "Chưa cấu hình Notion cho v2. Không ghi nhận bàn giao thành công.")
        if os.getenv("CONTENT_V2_ACCEPTANCE_MODE", "0") == "1" and (
            not os.getenv("NOTION_V2_DATABASE_ID", "").strip() or same_database(target, nc.NOTION_DATABASE_ID)
        ):
            raise HTTPException(503, "Chế độ nghiệm thu yêu cầu database v2 riêng; chưa ghi dữ liệu.")
        db = connect()
        try:
            old = db.execute("SELECT * FROM receipts WHERE request_id=? AND revision=?", (bundle.request_id, bundle.revision)).fetchone()
            latest = db.execute("SELECT MAX(revision) FROM receipts WHERE request_id=? AND status='received'", (bundle.request_id,)).fetchone()[0]
            bound = (old["database_id"] or nc.NOTION_DATABASE_ID) if old else None
            if old and not same_database(bound, target):
                raise HTTPException(409, "Bản bàn giao thuộc database khác. Hãy tạo phiên mới cho database thử.")
            if old and old["digest"] != digest:
                raise HTTPException(409, "Cùng request_id/phiên bản nhưng nội dung khác.")
            if latest is not None and bundle.revision < latest:
                raise HTTPException(409, "Phiên bản gửi tới đã cũ.")
            if old and not old["database_id"]:
                patch_receipt(db, bundle.request_id, bundle.revision, database_id=target)
            if old and old["status"] == "received":
                return {"success": True, "data": {"request_id": bundle.request_id, "revision": bundle.revision,
                    "notion_page_id": old["page_id"], "notion_database_id": target,
                    "payload_sha256": digest, "duplicate": True}, "error": None}
            if not old:
                db.execute("INSERT INTO receipts(request_id,revision,digest,status,database_id) VALUES(?,?,?,'pending',?)", (bundle.request_id, bundle.revision, digest, target))
                db.commit()
            # One atomic snapshot on a Docker volume retains the complete wire data.
            snapshot_path = folder() / f"{bundle.request_id}_r{bundle.revision}.json"
            temp = snapshot_path.with_suffix(".json.tmp")
            temp.write_text(canonical(raw), encoding="utf-8")
            temp.replace(snapshot_path)
            receipt = db.execute("SELECT * FROM receipts WHERE request_id=? AND revision=?", (bundle.request_id, bundle.revision)).fetchone()
            page_id = save_to_notion(bundle, db, receipt)
            patch_receipt(db, bundle.request_id, bundle.revision, status="received", page_id=page_id, error=None)
            return {"success": True, "data": {"request_id": bundle.request_id, "revision": bundle.revision,
                    "notion_page_id": page_id, "notion_database_id": target,
                    "payload_sha256": digest, "duplicate": False}, "error": None}
        except HTTPException:
            raise
        except Exception as exc:
            patch_receipt(db, bundle.request_id, bundle.revision, status="failed", error=type(exc).__name__)
            raise HTTPException(502, "Chưa lưu đầy đủ vào Notion; có thể gửi lại cùng phiên bản. " + type(exc).__name__)
        finally:
            db.close()


@router.get("/{request_id}/revisions/{revision}")
def read_snapshot(request_id: str, revision: int):
    with _lock:
        db = connect()
        try:
            receipt = db.execute("SELECT * FROM receipts WHERE request_id=? AND revision=?", (request_id, revision)).fetchone()
            if not receipt:
                raise HTTPException(404, "Chưa có bản bàn giao.")
            # Use the validated IDs from the receipt, never a path supplied by the caller.
            path = folder() / f"{receipt['request_id']}_r{receipt['revision']}.json"
            return {"success": receipt["status"] == "received", "status": receipt["status"],
                    "error": receipt["error"], "payload_sha256": receipt["digest"],
                    "notion_database_id": receipt["database_id"],
                    "data": json.loads(path.read_text(encoding="utf-8")) if path.exists() else None}
        finally:
            db.close()
