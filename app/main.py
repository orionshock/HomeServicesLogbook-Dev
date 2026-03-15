import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import get_connection, init_db


def _make_vendor_uid(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30]
    short = uuid.uuid4().hex[:4]
    return f"{slug}-{short}"


def _make_entry_uid() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short = uuid.uuid4().hex[:6]
    return f"{stamp}-{short}"


def _make_attachment_uid() -> str:
    return uuid.uuid4().hex


def _resolve_current_actor(_request: Request) -> dict[str, str]:
    # Temporary MVP actor resolution. Replace with real auth integration later.
    return {
        "actor_id": "devUser",
        "display_name": "devUser",
        "source": "hardcoded",
    }


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_stored_filename(original_name: str) -> str:
    ext = Path(original_name or "").suffix.lower()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short = uuid.uuid4().hex[:6]
    return f"{stamp}-{short}{ext}"

def _sanitize_original_filename(filename: str) -> str:
    basename = Path(filename or "").name
    sanitized = re.sub(r"\s+", "_", basename)
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", sanitized)
    sanitized = re.sub(r"_+", "_", sanitized)
    sanitized = sanitized.strip("._")
    return (sanitized or "uploaded-file")[:255]


def _escape_ics_text(value: str) -> str:
    escaped = (value or "").replace("\\", "\\\\")
    escaped = escaped.replace(";", "\\;").replace(",", "\\,")
    escaped = escaped.replace("\r\n", "\\n").replace("\n", "\\n")
    return escaped


def _build_ics_content(title: str, event_date: str, event_time: str, description: str) -> str:
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    event_uid = f"{uuid.uuid4().hex}@homeserviceslogbook.local"
    parsed_date = datetime.strptime(event_date, "%Y-%m-%d")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Home Services Logbook//MVP//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{event_uid}",
        f"DTSTAMP:{dtstamp}",
        f"SUMMARY:{_escape_ics_text(title)}",
    ]

    if event_time:
        parsed_time = datetime.strptime(event_time, "%H:%M")
        start_dt = datetime(
            year=parsed_date.year,
            month=parsed_date.month,
            day=parsed_date.day,
            hour=parsed_time.hour,
            minute=parsed_time.minute,
        )
        end_dt = start_dt + timedelta(hours=1)
        lines.append(f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M00')}")
        lines.append(f"DTEND:{end_dt.strftime('%Y%m%dT%H%M00')}")
    else:
        end_date = parsed_date + timedelta(days=1)
        lines.append(f"DTSTART;VALUE=DATE:{parsed_date.strftime('%Y%m%d')}")
        lines.append(f"DTEND;VALUE=DATE:{end_date.strftime('%Y%m%d')}")

    if description:
        lines.append(f"DESCRIPTION:{_escape_ics_text(description)}")

    lines.extend([
        "END:VEVENT",
        "END:VCALENDAR",
    ])
    return "\r\n".join(lines) + "\r\n"


def _slugify_for_filename(value: str, fallback: str = "calendar-event") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return (slug[:40] or fallback)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
BASE_DIR = Path(__file__).resolve().parent.parent

templates = Jinja2Templates(directory="templates")


def _render_template(request: Request, template_name: str, context: dict | None = None):
    payload = {
        "request": request,
        "current_actor": getattr(request.state, "current_actor", _resolve_current_actor(request)),
    }
    if context:
        payload.update(context)
    return templates.TemplateResponse(template_name, payload)


@app.middleware("http")
async def actor_context_middleware(request: Request, call_next):
    request.state.current_actor = _resolve_current_actor(request)
    return await call_next(request)


@app.get("/")
def read_root(request: Request):
    return _render_template(request, "home.html")


@app.get("/vendors/new")
def vendor_new_form(request: Request):
    return _render_template(request, "vendor_new.html")


@app.post("/vendors/new")
def vendor_new_submit(
    request: Request,
    name: str = Form(...),
    category: str = Form(""),
    account_number: str = Form(""),
    portal_url: str = Form(""),
    vendor_notes: str = Form(""),
):
    actor = request.state.current_actor["actor_id"]
    vendor_uid = _make_vendor_uid(name)
    now = _now_utc()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO vendors (vendor_uid, name, category, account_number, portal_url, vendor_notes, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                vendor_uid,
                name,
                category or None,
                account_number or None,
                portal_url or None,
                vendor_notes or None,
                now,
                actor,
            ),
        )
    return RedirectResponse(url=f"/vendor/{vendor_uid}", status_code=303)


@app.get("/vendors")
def vendor_list(request: Request, show_archived: int = 0):
    include_archived = show_archived == 1

    with get_connection() as conn:
        if include_archived:
            vendors = conn.execute(
                "SELECT * FROM vendors ORDER BY archived_at IS NOT NULL, name"
            ).fetchall()
        else:
            vendors = conn.execute(
                "SELECT * FROM vendors WHERE archived_at IS NULL ORDER BY name"
            ).fetchall()

    return _render_template(
        request,
        "vendors.html",
        {"vendors": vendors, "show_archived": include_archived},
    )


@app.post("/vendor/{vendor_uid}/archive")
def vendor_archive(request: Request, vendor_uid: str):
    actor = request.state.current_actor["actor_id"]

    with get_connection() as conn:
        exists = conn.execute(
            "SELECT id FROM vendors WHERE vendor_uid = ?",
            (vendor_uid,),
        ).fetchone()

        if exists is None:
            raise HTTPException(status_code=404, detail="Vendor not found")

        conn.execute(
            """
            UPDATE vendors
            SET
                archived_at = ?,
                updated_at = ?,
                updated_by = ?
            WHERE vendor_uid = ?
            """,
            (
                _now_utc(),
                _now_utc(),
                actor,
                vendor_uid,
            ),
        )

    return RedirectResponse(url="/vendors", status_code=303)


@app.get("/vendor/{vendor_uid}")
def vendor_detail(request: Request, vendor_uid: str):
    with get_connection() as conn:
        vendor = conn.execute(
            "SELECT * FROM vendors WHERE vendor_uid = ?",
            (vendor_uid,),
        ).fetchone()

        entries = conn.execute(
            """
            SELECT *
            FROM entries
            WHERE vendor_id = ?
              AND archived_at IS NULL
            ORDER BY created_at DESC, id DESC
            """,
            (vendor["id"],),
        ).fetchall() if vendor else []

        attachments_by_entry: dict[int, list] = {}
        if entries:
            entry_ids = [entry["id"] for entry in entries]
            placeholders = ",".join("?" for _ in entry_ids)
            attachments = conn.execute(
                f"""
                SELECT attachment_uid, entry_id, original_filename
                FROM attachments
                WHERE entry_id IN ({placeholders})
                ORDER BY id ASC
                """,
                tuple(entry_ids),
            ).fetchall()
            for item in attachments:
                attachments_by_entry.setdefault(item["entry_id"], []).append(item)

    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    return _render_template(
        request,
        "vendor_detail.html",
        {
            "vendor": vendor,
            "entries": entries,
            "attachments_by_entry": attachments_by_entry,
        },
    )


@app.get("/vendor/{vendor_uid}/edit")
def vendor_edit_form(request: Request, vendor_uid: str):
    with get_connection() as conn:
        vendor = conn.execute(
            "SELECT * FROM vendors WHERE vendor_uid = ?",
            (vendor_uid,),
        ).fetchone()

    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    return _render_template(request, "vendor_edit.html", {"vendor": vendor})


@app.post("/vendor/{vendor_uid}/edit")
def vendor_edit_submit(
    request: Request,
    vendor_uid: str,
    name: str = Form(...),
    category: str = Form(""),
    account_number: str = Form(""),
    name_on_account: str = Form(""),
    portal_url: str = Form(""),
    portal_username: str = Form(""),
    phone_on_file: str = Form(""),
    security_pin: str = Form(""),
    service_location: str = Form(""),
    vendor_notes: str = Form(""),
):
    actor = request.state.current_actor["actor_id"]

    with get_connection() as conn:
        exists = conn.execute(
            "SELECT id FROM vendors WHERE vendor_uid = ?",
            (vendor_uid,),
        ).fetchone()

        if exists is None:
            raise HTTPException(status_code=404, detail="Vendor not found")

        conn.execute(
            """
            UPDATE vendors
            SET
                name = ?,
                category = ?,
                account_number = ?,
                name_on_account = ?,
                portal_url = ?,
                portal_username = ?,
                phone_on_file = ?,
                security_pin = ?,
                service_location = ?,
                vendor_notes = ?,
                updated_at = ?,
                updated_by = ?
            WHERE vendor_uid = ?
            """,
            (
                name,
                category or None,
                account_number or None,
                name_on_account or None,
                portal_url or None,
                portal_username or None,
                phone_on_file or None,
                security_pin or None,
                service_location or None,
                vendor_notes or None,
                _now_utc(),
                actor,
                vendor_uid,
            ),
        )

    return RedirectResponse(url=f"/vendor/{vendor_uid}", status_code=303)


@app.get("/attachments/{attachment_uid}")
def attachment_download(attachment_uid: str):
    with get_connection() as conn:
        attachment = conn.execute(
            """
            SELECT attachment_uid, original_filename, relative_path, mime_type
            FROM attachments
            WHERE attachment_uid = ?
            """,
            (attachment_uid,),
        ).fetchone()

    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    rel_path = Path(attachment["relative_path"])
    abs_path = (BASE_DIR / rel_path).resolve()
    uploads_root = (BASE_DIR / "uploads").resolve()

    if uploads_root not in abs_path.parents or not abs_path.is_file():
        raise HTTPException(status_code=404, detail="Attachment file not found")

    return FileResponse(
        path=abs_path,
        media_type=attachment["mime_type"] or "application/octet-stream",
        filename=attachment["original_filename"],
    )


@app.get("/entry/{entry_uid}/edit")
def entry_edit_form(request: Request, entry_uid: str):
    with get_connection() as conn:
        entry = conn.execute(
            """
            SELECT e.*, v.vendor_uid, v.name AS vendor_name
            FROM entries e
            JOIN vendors v ON v.id = e.vendor_id
            WHERE e.entry_uid = ?
            """,
            (entry_uid,),
        ).fetchone()

    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    return _render_template(request, "entry_edit.html", {"entry": entry})


@app.post("/entry/{entry_uid}/edit")
def entry_edit_submit(
    request: Request,
    entry_uid: str,
    body_text: str = Form(""),
    vendor_reference: str = Form(""),
    rep_name: str = Form(""),
):
    actor = request.state.current_actor["actor_id"]

    with get_connection() as conn:
        entry = conn.execute(
            """
            SELECT e.id, v.vendor_uid
            FROM entries e
            JOIN vendors v ON v.id = e.vendor_id
            WHERE e.entry_uid = ?
            """,
            (entry_uid,),
        ).fetchone()

        if entry is None:
            raise HTTPException(status_code=404, detail="Entry not found")

        conn.execute(
            """
            UPDATE entries
            SET
                body_text = ?,
                vendor_reference = ?,
                rep_name = ?,
                updated_at = ?,
                updated_by = ?
            WHERE entry_uid = ?
            """,
            (
                body_text or None,
                vendor_reference or None,
                rep_name or None,
                _now_utc(),
                actor,
                entry_uid,
            ),
        )

    return RedirectResponse(url=f"/vendor/{entry['vendor_uid']}", status_code=303)


@app.post("/vendor/{vendor_uid}/entries")
def create_vendor_entry(
    request: Request,
    vendor_uid: str,
    body_text: str = Form(""),
    vendor_reference: str = Form(""),
    rep_name: str = Form(""),
    attachment: UploadFile | None = File(None),
):
    actor = request.state.current_actor["actor_id"]
    with get_connection() as conn:
        vendor = conn.execute(
            "SELECT id FROM vendors WHERE vendor_uid = ?",
            (vendor_uid,),
        ).fetchone()

        if vendor is None:
            raise HTTPException(status_code=404, detail="Vendor not found")

        cursor = conn.execute(
            """
            INSERT INTO entries (
                entry_uid,
                vendor_id,
                body_text,
                vendor_reference,
                rep_name,
                created_by,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _make_entry_uid(),
                vendor["id"],
                body_text or None,
                vendor_reference or None,
                rep_name or None,
                actor,
                _now_utc(),
            ),
        )

        entry_id = cursor.lastrowid

        if attachment and attachment.filename:
            raw_name = Path(attachment.filename).name
            if not Path(raw_name).suffix:
                raise HTTPException(
                    status_code=400,
                    detail="Attachment filename must include an extension",
                )

            now = datetime.now(timezone.utc)
            subdir = Path("uploads") / now.strftime("%Y") / now.strftime("%m")
            subdir.mkdir(parents=True, exist_ok=True)

            original_filename = _sanitize_original_filename(attachment.filename)
            if not Path(original_filename).suffix:
                raise HTTPException(
                    status_code=400,
                    detail="Attachment filename must include an extension",
                )

            stored_filename = _make_stored_filename(original_filename)
            disk_path = subdir / stored_filename
            file_bytes = attachment.file.read()

            with disk_path.open("wb") as out:
                out.write(file_bytes)

            conn.execute(
                """
                INSERT INTO attachments (
                    attachment_uid,
                    entry_id,
                    original_filename,
                    stored_filename,
                    relative_path,
                    mime_type,
                    file_size,
                    created_by,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _make_attachment_uid(),
                    entry_id,
                    original_filename,
                    stored_filename,
                    str(disk_path).replace("\\", "/"),
                    attachment.content_type,
                    len(file_bytes),
                    actor,
                    _now_utc(),
                ),
            )

    return RedirectResponse(url=f"/vendor/{vendor_uid}", status_code=303)


@app.post("/calendar/export")
def calendar_export_ics(
    title: str = Form(...),
    event_date: str = Form(...),
    event_time: str = Form(""),
    description: str = Form(""),
):
    clean_title = title.strip()
    clean_date = event_date.strip()
    clean_time = event_time.strip()
    clean_description = description.strip()

    if not clean_title:
        raise HTTPException(status_code=400, detail="Calendar title is required")

    try:
        datetime.strptime(clean_date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="event_date must use YYYY-MM-DD format") from exc

    if clean_time:
        try:
            datetime.strptime(clean_time, "%H:%M")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="event_time must use HH:MM format") from exc

    ics_body = _build_ics_content(clean_title, clean_date, clean_time, clean_description)
    file_name = f"{_slugify_for_filename(clean_title)}-{clean_date}.ics"

    return Response(
        content=ics_body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
