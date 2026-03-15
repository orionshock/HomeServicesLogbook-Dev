import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import (
    archive_vendor_by_uid,
    create_attachment,
    create_entry,
    create_vendor,
    delete_attachment_by_uid_for_entry,
    get_attachment_by_uid,
    get_entry_by_uid,
    get_vendor_by_uid,
    init_db,
    list_attachments_for_entry_id,
    list_attachments_for_entry_ids,
    list_entries_for_vendor,
    list_vendors,
    unarchive_vendor_by_uid,
    update_entry_by_uid,
    update_vendor_by_uid,
)


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
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _normalize_required_text(value: str, field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    return normalized


def _normalize_portal_url(value: str) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None

    # Allow common user input like "example.com" by defaulting to HTTPS.
    if "://" not in normalized:
        normalized = f"https://{normalized}"

    parsed = urlparse(normalized)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise HTTPException(
            status_code=400,
            detail="Portal URL must start with http:// or https://",
        )

    if not parsed.netloc or parsed.hostname is None:
        raise HTTPException(
            status_code=400,
            detail="Portal URL must include a valid host",
        )

    return normalized


def _validate_attachment_upload(upload: UploadFile) -> None:
    raw_name = Path(upload.filename or "").name
    if not Path(raw_name).suffix:
        raise HTTPException(
            status_code=400,
            detail="Attachment filename must include an extension",
        )

    declared_size = getattr(upload, "size", None)
    if declared_size is not None and declared_size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Attachment exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB size limit",
        )


def _get_submitted_attachments(attachments: list[UploadFile] | None) -> list[UploadFile]:
    if not attachments:
        return []
    return [upload for upload in attachments if upload and upload.filename]


def _delete_attachment_file(relative_path: str) -> None:
    rel_path = Path(relative_path)
    abs_path = (BASE_DIR / rel_path).resolve()
    uploads_root = (BASE_DIR / "uploads").resolve()

    if uploads_root not in abs_path.parents:
        return

    if abs_path.exists() and abs_path.is_file():
        abs_path.unlink()


def _store_uploaded_attachment(upload: UploadFile, entry_id: int, actor: str) -> None:
    _validate_attachment_upload(upload)

    now = datetime.now(timezone.utc)
    relative_dir = Path("uploads") / now.strftime("%Y") / now.strftime("%m")
    absolute_dir = BASE_DIR / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    original_filename = _sanitize_original_filename(upload.filename or "")
    if not Path(original_filename).suffix:
        raise HTTPException(
            status_code=400,
            detail="Attachment filename must include an extension",
        )

    stored_filename = _make_stored_filename(original_filename)
    relative_path = relative_dir / stored_filename
    disk_path = absolute_dir / stored_filename

    bytes_written = 0
    chunk_size = 1024 * 1024
    try:
        with disk_path.open("wb") as out:
            while True:
                chunk = upload.file.read(chunk_size)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Attachment exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB size limit",
                    )
                out.write(chunk)
    except HTTPException:
        if disk_path.exists():
            disk_path.unlink()
        raise
    except Exception:
        if disk_path.exists():
            disk_path.unlink()
        raise
    finally:
        upload.file.close()

    create_attachment(
        attachment_uid=_make_attachment_uid(),
        entry_id=entry_id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        relative_path=str(relative_path).replace("\\", "/"),
        mime_type=upload.content_type,
        file_size=bytes_written,
        created_by=actor,
        created_at=_now_utc(),
    )


def _store_uploaded_attachments(attachments: list[UploadFile], entry_id: int, actor: str) -> None:
    for upload in attachments:
        _store_uploaded_attachment(upload, entry_id=entry_id, actor=actor)


def _render_template(request: Request, template_name: str, context: dict | None = None):
    payload = {
        "request": request,
        "current_actor": getattr(request.state, "current_actor", _resolve_current_actor(request)),
    }
    if context:
        payload.update(context)
    return templates.TemplateResponse(template_name, payload)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    status_code = exc.status_code
    if status_code == 404:
        response = _render_template(
            request,
            "404.html",
            {"message": str(exc.detail or "The requested page could not be found.")},
        )
        response.status_code = 404
        return response

    if status_code >= 400:
        response = _render_template(
            request,
            "error.html",
            {
                "status_code": status_code,
                "message": str(exc.detail or "The request could not be processed."),
            },
        )
        response.status_code = status_code
        return response

    return _render_template(
        request,
        "error.html",
        {"status_code": 500, "message": "An unexpected error occurred."},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, _exc: RequestValidationError):
    response = _render_template(
        request,
        "error.html",
        {
            "status_code": 400,
            "message": "Some form fields were missing or invalid.",
        },
    )
    response.status_code = 400
    return response


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, _exc: Exception):
    response = _render_template(
        request,
        "error.html",
        {
            "status_code": 500,
            "message": "An unexpected error occurred. Please try again.",
        },
    )
    response.status_code = 500
    return response


@app.middleware("http")
async def actor_context_middleware(request: Request, call_next):
    request.state.current_actor = _resolve_current_actor(request)
    return await call_next(request)


@app.get("/")
def read_root(request: Request):
    return _render_template(request, "home.html")


@app.get("/vendors/new")
def vendor_new_form(request: Request):
    return _render_template(
        request,
        "vendor_form.html",
        {
            "vendor": None,
            "is_edit": False,
            "form_action": "/vendors/new",
            "submit_label": "Save Vendor",
        },
    )


@app.post("/vendors/new")
def vendor_new_submit(
    request: Request,
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
    clean_name = _normalize_required_text(name, "Vendor name")
    clean_portal_url = _normalize_portal_url(portal_url)
    vendor_uid = _make_vendor_uid(clean_name)
    now = _now_utc()
    create_vendor(
        vendor_uid=vendor_uid,
        name=clean_name,
        category=category or None,
        account_number=account_number or None,
        name_on_account=name_on_account or None,
        portal_url=clean_portal_url,
        portal_username=portal_username or None,
        phone_on_file=phone_on_file or None,
        security_pin=security_pin or None,
        service_location=service_location or None,
        vendor_notes=vendor_notes or None,
        created_at=now,
        created_by=actor,
    )
    return RedirectResponse(url=f"/vendor/{vendor_uid}", status_code=303)


@app.get("/vendors")
def vendor_list(request: Request, show_archived: int | None = None):
    query_has_preference = "show_archived" in request.query_params
    if query_has_preference:
        include_archived = show_archived == 1
    else:
        include_archived = request.cookies.get("show_archived_vendors") == "1"

    vendors = list_vendors(include_archived)
    response = _render_template(
        request,
        "vendors.html",
        {"vendors": vendors, "show_archived": include_archived},
    )

    if query_has_preference:
        response.set_cookie(
            key="show_archived_vendors",
            value="1" if include_archived else "0",
            max_age=60 * 60 * 24 * 365,
            path="/",
            samesite="lax",
            httponly=True,
        )

    return response


@app.post("/vendor/{vendor_uid}/archive")
def vendor_archive(request: Request, vendor_uid: str):
    actor = request.state.current_actor["actor_id"]
    now = _now_utc()
    found = archive_vendor_by_uid(vendor_uid, archived_at=now, updated_by=actor)
    if not found:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return RedirectResponse(url="/vendors", status_code=303)


@app.post("/vendor/{vendor_uid}/unarchive")
def vendor_unarchive(request: Request, vendor_uid: str):
    actor = request.state.current_actor["actor_id"]
    now = _now_utc()
    found = unarchive_vendor_by_uid(vendor_uid, updated_at=now, updated_by=actor)
    if not found:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return RedirectResponse(url=f"/vendor/{vendor_uid}", status_code=303)


@app.get("/vendor/{vendor_uid}")
def vendor_detail(request: Request, vendor_uid: str):
    vendor = get_vendor_by_uid(vendor_uid)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    entries = list_entries_for_vendor(vendor["id"])
    attachments_by_entry: dict[int, list] = {}
    for item in list_attachments_for_entry_ids([e["id"] for e in entries]):
        attachments_by_entry.setdefault(item["entry_id"], []).append(item)

    return _render_template(
        request,
        "vendor_detail.html",
        {
            "vendor": vendor,
            "entries": entries,
            "attachments_by_entry": attachments_by_entry,
        },
    )


@app.get("/vendor/{vendor_uid}/entries/new")
def vendor_entry_new_form(request: Request, vendor_uid: str):
    vendor = get_vendor_by_uid(vendor_uid)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if vendor["archived_at"]:
        raise HTTPException(
            status_code=400,
            detail="Archived vendors cannot accept new entries. Unarchive vendor to continue.",
        )

    entries = list_entries_for_vendor(vendor["id"])
    attachments_by_entry: dict[int, list] = {}
    for item in list_attachments_for_entry_ids([e["id"] for e in entries]):
        attachments_by_entry.setdefault(item["entry_id"], []).append(item)

    return _render_template(
        request,
        "entry_form.html",
        {
            "mode": "create",
            "vendor": vendor,
            "entry": None,
            "entry_attachments": [],
            "entries": entries,
            "attachments_by_entry": attachments_by_entry,
            "form_action": f"/vendor/{vendor_uid}/entries",
            "submit_label": "Save Entry",
        },
    )


@app.get("/vendor/{vendor_uid}/edit")
def vendor_edit_form(request: Request, vendor_uid: str):
    vendor = get_vendor_by_uid(vendor_uid)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    return _render_template(
        request,
        "vendor_form.html",
        {
            "vendor": vendor,
            "is_edit": True,
            "form_action": f"/vendor/{vendor_uid}/edit",
            "submit_label": "Save Changes",
        },
    )


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
    clean_name = _normalize_required_text(name, "Vendor name")
    clean_portal_url = _normalize_portal_url(portal_url)
    if get_vendor_by_uid(vendor_uid) is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    update_vendor_by_uid(
        vendor_uid=vendor_uid,
        name=clean_name,
        category=category or None,
        account_number=account_number or None,
        name_on_account=name_on_account or None,
        portal_url=clean_portal_url,
        portal_username=portal_username or None,
        phone_on_file=phone_on_file or None,
        security_pin=security_pin or None,
        service_location=service_location or None,
        vendor_notes=vendor_notes or None,
        updated_at=_now_utc(),
        updated_by=actor,
    )
    return RedirectResponse(url=f"/vendor/{vendor_uid}", status_code=303)


@app.get("/attachments/{attachment_uid}")
def attachment_download(attachment_uid: str):
    attachment = get_attachment_by_uid(attachment_uid)
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
    entry = get_entry_by_uid(entry_uid)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    vendor = get_vendor_by_uid(entry["vendor_uid"])
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    entry_attachments = list_attachments_for_entry_id(entry["id"])
    entries = list_entries_for_vendor(vendor["id"])
    attachments_by_entry: dict[int, list] = {}
    for item in list_attachments_for_entry_ids([e["id"] for e in entries]):
        attachments_by_entry.setdefault(item["entry_id"], []).append(item)

    return _render_template(
        request,
        "entry_form.html",
        {
            "mode": "edit",
            "vendor": vendor,
            "entry": entry,
            "entry_attachments": entry_attachments,
            "entries": entries,
            "attachments_by_entry": attachments_by_entry,
            "form_action": f"/entry/{entry_uid}/edit",
            "submit_label": "Save Entry Changes",
        },
    )


@app.post("/entry/{entry_uid}/edit")
def entry_edit_submit(
    request: Request,
    entry_uid: str,
    body_text: str = Form(""),
    vendor_reference: str = Form(""),
    rep_name: str = Form(""),
    remove_attachment_uids: list[str] | None = Form(None),
    attachments: list[UploadFile] | None = File(None),
):
    actor = request.state.current_actor["actor_id"]
    entry = get_entry_by_uid(entry_uid)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    new_attachments = _get_submitted_attachments(attachments)
    for upload in new_attachments:
        _validate_attachment_upload(upload)

    update_entry_by_uid(
        entry_uid=entry_uid,
        body_text=body_text or None,
        vendor_reference=vendor_reference or None,
        rep_name=rep_name or None,
        updated_at=_now_utc(),
        updated_by=actor,
    )

    for attachment_uid in set(remove_attachment_uids or []):
        deleted_attachment = delete_attachment_by_uid_for_entry(entry["id"], attachment_uid)
        if deleted_attachment is not None:
            _delete_attachment_file(deleted_attachment["relative_path"])

    _store_uploaded_attachments(new_attachments, entry_id=entry["id"], actor=actor)

    return RedirectResponse(url=f"/vendor/{entry['vendor_uid']}", status_code=303)


@app.post("/vendor/{vendor_uid}/entries")
def create_vendor_entry(
    request: Request,
    vendor_uid: str,
    body_text: str = Form(""),
    vendor_reference: str = Form(""),
    rep_name: str = Form(""),
    attachments: list[UploadFile] | None = File(None),
):
    actor = request.state.current_actor["actor_id"]
    vendor = get_vendor_by_uid(vendor_uid)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if vendor["archived_at"]:
        raise HTTPException(
            status_code=400,
            detail="Archived vendors cannot accept new entries. Unarchive vendor to continue.",
        )

    new_attachments = _get_submitted_attachments(attachments)
    for upload in new_attachments:
        _validate_attachment_upload(upload)

    entry_id = create_entry(
        entry_uid=_make_entry_uid(),
        vendor_id=vendor["id"],
        body_text=body_text or None,
        vendor_reference=vendor_reference or None,
        rep_name=rep_name or None,
        created_by=actor,
        created_at=_now_utc(),
    )

    _store_uploaded_attachments(new_attachments, entry_id=entry_id, actor=actor)

    return RedirectResponse(url=f"/vendor/{vendor_uid}", status_code=303)


@app.post("/calendar/export")
def calendar_export_ics(
    title: str = Form(...),
    event_date: str = Form(...),
    event_time: str = Form(""),
    description: str = Form(""),
):
    clean_title = _normalize_required_text(title, "Calendar title")
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
