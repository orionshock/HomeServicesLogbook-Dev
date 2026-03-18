from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import uuid

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, RedirectResponse

from app.db import (
    create_attachment,
    create_entry,
    delete_attachment_by_uid_for_entry,
    get_attachment_by_uid,
    get_entry_by_uid,
    get_vendor_by_uid,
    list_attachments_for_entry_id,
    list_attachments_for_entry_ids,
    list_entries_for_vendor,
    list_labels,
    list_labels_for_entry_id,
    list_labels_for_vendor_id,
    replace_entry_labels,
    resolve_submitted_labels,
    update_entry_by_uid,
)
from app.routes import BASE_DIR, MAX_UPLOAD_BYTES, render_template
from app.utils import (
    make_uid,
    normalize_label_name,
    normalize_required_text,
    utc_now_iso,
)

router = APIRouter()


def normalize_entry_interaction_at_utc(entry_interaction_at_utc: str) -> str | None:
    raw_value = (entry_interaction_at_utc or "").strip()
    if not raw_value:
        return None

    parsed_iso = raw_value.replace("Z", "+00:00")
    try:
        parsed_dt = datetime.fromisoformat(parsed_iso)
    except ValueError as exc:
        raise ValueError("Interaction Date must be a valid timestamp") from exc

    if parsed_dt.tzinfo is None or parsed_dt.utcoffset() != timedelta(0):
        raise ValueError("Interaction Date must be UTC (offset 00:00)")

    return parsed_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def make_stored_filename(original_name: str) -> str:
    ext = Path(original_name or "").suffix.lower()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short = uuid.uuid4().hex[:6]
    return f"{stamp}-{short}{ext}"


def sanitize_original_filename(filename: str) -> str:
    basename = Path(filename or "").name
    sanitized = re.sub(r"\s+", "_", basename)
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", sanitized)
    sanitized = re.sub(r"_+", "_", sanitized)
    sanitized = sanitized.strip("._")
    return (sanitized or "uploaded-file")[:255]


def validate_attachment_upload(upload: UploadFile, max_upload_bytes: int) -> None:
    raw_name = Path(upload.filename or "").name
    if not Path(raw_name).suffix:
        raise ValueError("Attachment filename must include an extension")

    declared_size = getattr(upload, "size", None)
    if declared_size is not None and declared_size > max_upload_bytes:
        raise ValueError(f"Attachment exceeds {max_upload_bytes // (1024 * 1024)} MB size limit")


def get_submitted_attachments(attachments: list[UploadFile] | None) -> list[UploadFile]:
    if not attachments:
        return []
    return [upload for upload in attachments if upload and upload.filename]


def delete_attachment_file(base_dir: Path, attachment_relative_path: str) -> None:
    rel_path = Path(attachment_relative_path)
    abs_path = (base_dir / rel_path).resolve()
    uploads_root = (base_dir / "uploads").resolve()

    if uploads_root not in abs_path.parents:
        return

    if abs_path.exists() and abs_path.is_file():
        abs_path.unlink()


def _escape_ics_text(value: str) -> str:
    escaped = (value or "").replace("\\", "\\\\")
    escaped = escaped.replace(";", "\\;").replace(",", "\\,")
    escaped = escaped.replace("\r\n", "\\n").replace("\n", "\\n")
    return escaped


def build_ics_content(title: str, event_date: str, event_time: str, description: str) -> str:
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    event_uid = f"{uuid.uuid4().hex}@homeserviceslogbook.local"
    parsed_date = datetime.strptime(event_date, "%Y-%m-%d")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Home Services Logbook//Development//EN",
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


def slugify_for_filename(value: str, fallback: str = "calendar-event") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:40] or fallback


def _store_uploaded_attachment(
    upload: UploadFile,
    entry_id: int,
    actor: str,
) -> None:
    validate_attachment_upload(upload, MAX_UPLOAD_BYTES)

    now = datetime.now(timezone.utc)
    relative_dir = Path("uploads") / now.strftime("%Y") / now.strftime("%m")
    absolute_dir = BASE_DIR / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    attachment_original_filename = sanitize_original_filename(upload.filename or "")
    if not Path(attachment_original_filename).suffix:
        raise HTTPException(
            status_code=400,
            detail="Attachment filename must include an extension",
        )

    attachment_stored_filename = make_stored_filename(attachment_original_filename)
    attachment_relative_path = relative_dir / attachment_stored_filename
    disk_path = absolute_dir / attachment_stored_filename

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
        attachment_uid=make_uid("attachment"),
        entry_id=entry_id,
        attachment_original_filename=attachment_original_filename,
        attachment_stored_filename=attachment_stored_filename,
        attachment_relative_path=str(attachment_relative_path).replace("\\", "/"),
        attachment_mime_type=upload.content_type,
        attachment_file_size=bytes_written,
        attachment_created_by=actor,
        attachment_created_at=utc_now_iso(),
    )


def _store_uploaded_attachments(attachments: list[UploadFile], entry_id: int, actor: str) -> None:
    for upload in attachments:
        _store_uploaded_attachment(upload, entry_id=entry_id, actor=actor)


def _normalize_optional_text(value: str) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def _select_labels_for_form(
    all_labels: list,
    label_uids: list[str],
    new_label_names: list[str],
) -> tuple[list, list[str]]:
    labels_by_uid = {str(item["label_uid"]): item for item in all_labels}
    selected_labels: list = []
    seen_uids: set[str] = set()
    for raw_uid in label_uids:
        clean_uid = (raw_uid or "").strip()
        if not clean_uid or clean_uid in seen_uids:
            continue
        row = labels_by_uid.get(clean_uid)
        if row is None:
            continue
        seen_uids.add(clean_uid)
        selected_labels.append(row)

    normalized_new_names: list[str] = []
    seen_name_keys: set[str] = set()
    for raw_name in new_label_names:
        normalized_name = normalize_label_name(raw_name)
        if not normalized_name:
            continue
        name_key = normalized_name.lower()
        if name_key in seen_name_keys:
            continue
        seen_name_keys.add(name_key)
        normalized_new_names.append(normalized_name)

    return selected_labels, normalized_new_names


def _render_entry_form(
    request: Request,
    *,
    mode: str,
    vendor,
    entry,
    form_action: str,
    submit_label: str,
    selected_labels: list,
    submitted_new_label_names: list[str] | None = None,
    current_entry_uid: str | None = None,
    remove_attachment_uids_selected: list[str] | None = None,
    errors: dict[str, str] | None = None,
    form_error: str | None = None,
    status_code: int = 200,
):
    entries = list_entries_for_vendor(vendor["id"])
    attachments_by_entry: dict[int, list] = {}
    labels_by_entry: dict[int, list] = {}
    for item in list_attachments_for_entry_ids([e["id"] for e in entries]):
        attachments_by_entry.setdefault(item["entry_id"], []).append(item)
    for item in entries:
        labels_by_entry[item["id"]] = list_labels_for_entry_id(item["id"])

    if mode == "edit":
        entry_crumb_label = entry["entry_title"] if entry and entry.get("entry_title") else current_entry_uid
        breadcrumbs = [
            {"label": "Home", "url": "/"},
            {"label": "Vendors", "url": "/vendors"},
            {"label": vendor["vendor_name"], "url": f"/vendor/{vendor['vendor_uid']}"},
            {"label": f"Edit Entry - {entry_crumb_label}", "url": None},
        ]
        entry_attachments = list_attachments_for_entry_id(entry["id"])
    else:
        breadcrumbs = [
            {"label": "Home", "url": "/"},
            {"label": "Vendors", "url": "/vendors"},
            {"label": vendor["vendor_name"], "url": f"/vendor/{vendor['vendor_uid']}"},
            {"label": "New Entry", "url": None},
        ]
        entry_attachments = []

    response = render_template(
        request,
        "entry_form.html",
        {
            "breadcrumbs": breadcrumbs,
            "mode": mode,
            "vendor": vendor,
            "vendor_labels": list_labels_for_vendor_id(vendor["id"]),
            "entry": entry,
            "entry_attachments": entry_attachments,
            "entries": entries,
            "attachments_by_entry": attachments_by_entry,
            "labels_by_entry": labels_by_entry,
            "all_labels": list_labels(),
            "selected_labels": selected_labels,
            "submitted_new_label_names": submitted_new_label_names or [],
            "field_label": "Labels",
            "current_entry_uid": current_entry_uid,
            "form_action": form_action,
            "submit_label": submit_label,
            "remove_attachment_uids_selected": remove_attachment_uids_selected or [],
            "errors": errors or {},
            "form_error": form_error or ("Please fix the highlighted fields." if errors else None),
        },
    )
    response.status_code = status_code
    return response


@router.get("/vendor/{vendor_uid}/entries/new")
def vendor_entry_new_form(request: Request, vendor_uid: str):
    vendor = get_vendor_by_uid(vendor_uid)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if vendor["vendor_archived_at"]:
        raise HTTPException(
            status_code=400,
            detail="Archived vendors cannot accept new entries. Unarchive vendor to continue.",
        )

    return _render_entry_form(
        request,
        mode="create",
        vendor=vendor,
        entry=None,
        selected_labels=[],
        form_action=f"/vendor/{vendor_uid}/entries",
        submit_label="Save Entry",
    )


@router.get("/attachments/{attachment_uid}")
def attachment_download(attachment_uid: str):
    attachment = get_attachment_by_uid(attachment_uid)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    rel_path = Path(attachment["attachment_relative_path"])
    abs_path = (BASE_DIR / rel_path).resolve()
    uploads_root = (BASE_DIR / "uploads").resolve()

    if uploads_root not in abs_path.parents or not abs_path.is_file():
        raise HTTPException(status_code=404, detail="Attachment file not found")

    return FileResponse(
        path=abs_path,
        media_type=attachment["attachment_mime_type"] or "application/octet-stream",
        filename=attachment["attachment_original_filename"],
    )


@router.get("/entry/{entry_uid}/edit")
def entry_edit_form(request: Request, entry_uid: str):
    entry = get_entry_by_uid(entry_uid)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    vendor = get_vendor_by_uid(entry["vendor_uid"])
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    return _render_entry_form(
        request,
        mode="edit",
        vendor=vendor,
        entry=dict(entry),
        selected_labels=list_labels_for_entry_id(entry["id"]),
        current_entry_uid=entry_uid,
        form_action=f"/entry/{entry_uid}/edit",
        submit_label="Save Entry Changes",
    )


@router.post("/entry/{entry_uid}/edit")
def entry_edit_submit(
    request: Request,
    entry_uid: str,
    entry_body_text: str = Form(""),
    entry_title: str = Form(""),
    entry_interaction_at: str = Form(""),
    entry_rep_name: str = Form(""),
    label_uids: list[str] | None = Form(None),
    new_label_names: list[str] | None = Form(None),
    remove_attachment_uids: list[str] | None = Form(None),
    attachments: list[UploadFile] | None = File(None),
):
    actor = request.state.current_actor["actor_id"]
    entry = get_entry_by_uid(entry_uid)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    vendor = get_vendor_by_uid(entry["vendor_uid"])
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    all_labels = list_labels()
    selected_labels, normalized_new_label_names = _select_labels_for_form(
        all_labels,
        label_uids or [],
        new_label_names or [],
    )
    submitted_entry = {
        "id": entry["id"],
        "entry_uid": entry_uid,
        "entry_title": entry_title,
        "entry_interaction_at": entry_interaction_at,
        "entry_body_text": entry_body_text,
        "entry_rep_name": entry_rep_name,
    }
    selected_remove_attachment_uids = [item for item in (remove_attachment_uids or []) if item]
    errors: dict[str, str] = {}

    new_attachments = get_submitted_attachments(attachments)
    for upload in new_attachments:
        try:
            validate_attachment_upload(upload, MAX_UPLOAD_BYTES)
        except ValueError as exc:
            errors["attachments"] = str(exc)
            break

    try:
        clean_entry_interaction_at = normalize_entry_interaction_at_utc(entry_interaction_at)
    except ValueError as exc:
        errors["entry_interaction_at"] = str(exc)
        clean_entry_interaction_at = None

    if errors:
        return _render_entry_form(
            request,
            mode="edit",
            vendor=vendor,
            entry=submitted_entry,
            selected_labels=selected_labels,
            submitted_new_label_names=normalized_new_label_names,
            current_entry_uid=entry_uid,
            form_action=f"/entry/{entry_uid}/edit",
            submit_label="Save Entry Changes",
            remove_attachment_uids_selected=selected_remove_attachment_uids,
            errors=errors,
            status_code=400,
        )

    now = utc_now_iso()
    try:
        update_entry_by_uid(
            entry_uid=entry_uid,
            entry_title=_normalize_optional_text(entry_title),
            entry_interaction_at=clean_entry_interaction_at,
            entry_body_text=_normalize_optional_text(entry_body_text),
            entry_rep_name=_normalize_optional_text(entry_rep_name),
            entry_updated_at=now,
            entry_updated_by=actor,
        )
    except ValueError as exc:
        return _render_entry_form(
            request,
            mode="edit",
            vendor=vendor,
            entry=submitted_entry,
            selected_labels=selected_labels,
            submitted_new_label_names=normalized_new_label_names,
            current_entry_uid=entry_uid,
            form_action=f"/entry/{entry_uid}/edit",
            submit_label="Save Entry Changes",
            remove_attachment_uids_selected=selected_remove_attachment_uids,
            form_error=str(exc),
            status_code=400,
        )

    resolved_label_ids = resolve_submitted_labels(
        label_uids=label_uids or [],
        new_label_names=new_label_names or [],
        actor=actor,
        now=now,
    )
    replace_entry_labels(entry["id"], resolved_label_ids)

    for attachment_uid in set(remove_attachment_uids or []):
        deleted_attachment = delete_attachment_by_uid_for_entry(entry["id"], attachment_uid)
        if deleted_attachment is not None:
            delete_attachment_file(BASE_DIR, deleted_attachment["attachment_relative_path"])

    _store_uploaded_attachments(new_attachments, entry_id=entry["id"], actor=actor)

    return RedirectResponse(url=f"/vendor/{entry['vendor_uid']}", status_code=303)


@router.post("/vendor/{vendor_uid}/entries")
def create_vendor_entry(
    request: Request,
    vendor_uid: str,
    entry_body_text: str = Form(""),
    entry_title: str = Form(""),
    entry_interaction_at: str = Form(""),
    entry_rep_name: str = Form(""),
    label_uids: list[str] | None = Form(None),
    new_label_names: list[str] | None = Form(None),
    attachments: list[UploadFile] | None = File(None),
):
    actor = request.state.current_actor["actor_id"]
    vendor = get_vendor_by_uid(vendor_uid)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if vendor["vendor_archived_at"]:
        raise HTTPException(
            status_code=400,
            detail="Archived vendors cannot accept new entries. Unarchive vendor to continue.",
        )

    all_labels = list_labels()
    selected_labels, normalized_new_label_names = _select_labels_for_form(
        all_labels,
        label_uids or [],
        new_label_names or [],
    )
    submitted_entry = {
        "entry_title": entry_title,
        "entry_interaction_at": entry_interaction_at,
        "entry_body_text": entry_body_text,
        "entry_rep_name": entry_rep_name,
    }
    errors: dict[str, str] = {}

    new_attachments = get_submitted_attachments(attachments)
    for upload in new_attachments:
        try:
            validate_attachment_upload(upload, MAX_UPLOAD_BYTES)
        except ValueError as exc:
            errors["attachments"] = str(exc)
            break

    try:
        clean_entry_interaction_at = normalize_entry_interaction_at_utc(entry_interaction_at)
    except ValueError as exc:
        errors["entry_interaction_at"] = str(exc)
        clean_entry_interaction_at = None

    has_submitted_label_values = bool(label_uids) or any(
        normalize_label_name(item or "") for item in (new_label_names or [])
    )

    # Skip record creation if every field is blank and no files were attached.
    if not any([
        entry_body_text.strip(),
        entry_title.strip(),
        entry_interaction_at.strip(),
        entry_rep_name.strip(),
        new_attachments,
        has_submitted_label_values,
    ]):
        return RedirectResponse(url=f"/vendor/{vendor_uid}", status_code=303)

    if errors:
        return _render_entry_form(
            request,
            mode="create",
            vendor=vendor,
            entry=submitted_entry,
            selected_labels=selected_labels,
            submitted_new_label_names=normalized_new_label_names,
            form_action=f"/vendor/{vendor_uid}/entries",
            submit_label="Save Entry",
            errors=errors,
            status_code=400,
        )

    now = utc_now_iso()
    try:
        entry_id = create_entry(
            entry_uid=make_uid("entry"),
            vendor_id=vendor["id"],
            entry_title=_normalize_optional_text(entry_title),
            entry_interaction_at=clean_entry_interaction_at,
            entry_body_text=_normalize_optional_text(entry_body_text),
            entry_rep_name=_normalize_optional_text(entry_rep_name),
            entry_created_by=actor,
            entry_created_at=now,
        )
    except ValueError as exc:
        return _render_entry_form(
            request,
            mode="create",
            vendor=vendor,
            entry=submitted_entry,
            selected_labels=selected_labels,
            submitted_new_label_names=normalized_new_label_names,
            form_action=f"/vendor/{vendor_uid}/entries",
            submit_label="Save Entry",
            form_error=str(exc),
            status_code=400,
        )

    resolved_label_ids = resolve_submitted_labels(
        label_uids=label_uids or [],
        new_label_names=new_label_names or [],
        actor=actor,
        now=now,
    )
    replace_entry_labels(entry_id, resolved_label_ids)

    _store_uploaded_attachments(new_attachments, entry_id=entry_id, actor=actor)

    return RedirectResponse(url=f"/vendor/{vendor_uid}", status_code=303)


@router.post("/calendar/export")
def calendar_export_ics(
    title: str = Form(""),
    event_date: str = Form(...),
    event_time: str = Form(""),
    description: str = Form(""),
):
    try:
        clean_title = normalize_required_text(title, "Calendar title")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    clean_date = event_date.strip()
    clean_time = event_time.strip()
    clean_description = description.strip()

    try:
        datetime.strptime(clean_date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="event_date must use YYYY-MM-DD format") from exc

    if clean_time:
        try:
            datetime.strptime(clean_time, "%H:%M")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="event_time must use HH:MM format") from exc

    ics_body = build_ics_content(clean_title, clean_date, clean_time, clean_description)
    file_name = f"{slugify_for_filename(clean_title)}-{clean_date}.ics"

    return Response(
        content=ics_body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
