"""Entry and attachment route handlers, including ICS export helpers."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from urllib.parse import urlsplit
import uuid

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, RedirectResponse

from app.db import (
    create_entry_for_vendor_uid,
    delete_entry_by_uid,
    delete_entry_attachment_by_uid,
    get_attachment_by_uid,
    get_entry_by_uid,
    get_entry_labels_by_uid,
    list_entry_vendor_picker_rows,
    get_vendor_by_uid,
    get_vendor_entry_form_context,
    list_labels,
    replace_entry_labels_by_uid,
    resolve_attachment_disk_path,
    resolve_submitted_labels,
    store_attachment_uploads_for_entry_uid,
    update_entry_by_uid,
)
from app.routes import MAX_UPLOAD_BYTES, path_for, render_template
from app.utils import (
    make_uid,
    normalize_label_name,
    normalize_optional_text,
    normalize_required_text,
    utc_now_iso,
)

router = APIRouter()


def _safe_internal_return_target(value: str | None) -> str | None:
    """Allow only safe internal redirect targets."""
    target = (value or "").strip()
    if not target:
        return None

    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    if not target.startswith("/"):
        return None
    if target.startswith("//"):
        return None

    return target


def normalize_entry_interaction_at_utc(entry_interaction_at_utc: str) -> str | None:
    """Normalize optional interaction timestamp and require UTC offsets."""
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


def validate_attachment_upload(upload: UploadFile, max_upload_bytes: int) -> None:
    """Validate attachment filename shape and declared size before processing."""
    raw_name = Path(upload.filename or "").name
    if not Path(raw_name).suffix:
        raise ValueError("Attachment filename must include an extension")

    declared_size = getattr(upload, "size", None)
    if declared_size is not None and declared_size > max_upload_bytes:
        raise ValueError(f"Attachment exceeds {max_upload_bytes // (1024 * 1024)} MB size limit")


def get_submitted_attachments(attachments: list[UploadFile] | None) -> list[UploadFile]:
    """Return only non-empty uploaded file objects from form input."""
    if not attachments:
        return []
    return [upload for upload in attachments if upload and upload.filename]


def _escape_ics_text(value: str) -> str:
    """Escape text for safe insertion into ICS properties."""
    escaped = (value or "").replace("\\", "\\\\")
    escaped = escaped.replace(";", "\\;").replace(",", "\\,")
    escaped = escaped.replace("\r\n", "\\n").replace("\n", "\\n")
    return escaped


def build_ics_content(title: str, event_date: str, event_time: str, description: str) -> str:
    """Build a minimal iCalendar payload for a single event."""
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
    """Generate a filesystem-friendly slug for download filenames."""
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:40] or fallback


def _select_labels_for_form(
    all_labels: list,
    label_uids: list[str],
    new_label_names: list[str],
) -> tuple[list, list[str]]:
    """Resolve selected existing labels plus normalized new label names for form rendering."""
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
    return_next: str | None = None,
    status_code: int = 200,
):
    """Render create/edit entry form with aggregated UID-shaped context."""
    form_context = get_vendor_entry_form_context(
        vendor_uid=vendor["vendor_uid"],
        entry_uid_to_edit=current_entry_uid,
    )
    entries = form_context["entries"]
    attachments_by_entry_uid = form_context["attachments_by_entry_uid"]
    labels_by_entry_uid = form_context["labels_by_entry_uid"]
    entry_attachments = form_context["entry_attachments"]
    vendor_labels = form_context["vendor_labels"]
    all_labels = form_context["all_labels"]

    if mode == "edit":
        entry_crumb_label = entry["entry_title"] if entry and entry.get("entry_title") else current_entry_uid
        breadcrumbs = [
            {"label": "Home", "url": path_for(request, "read_root")},
            {"label": "Vendors", "url": path_for(request, "vendor_list")},
            {"label": vendor["vendor_name"], "url": path_for(request, "vendor_detail", vendor_uid=vendor["vendor_uid"])},
            {"label": f"Edit Entry - {entry_crumb_label}", "url": None},
        ]
    else:
        breadcrumbs = [
            {"label": "Home", "url": path_for(request, "read_root")},
            {"label": "Vendors", "url": path_for(request, "vendor_list")},
            {"label": vendor["vendor_name"], "url": path_for(request, "vendor_detail", vendor_uid=vendor["vendor_uid"])},
            {"label": "New Entry", "url": None},
        ]

    response = render_template(
        request,
        "entry_form.html",
        {
            "breadcrumbs": breadcrumbs,
            "mode": mode,
            "vendor": vendor,
            "vendor_labels": vendor_labels,
            "entry": entry,
            "entry_attachments": entry_attachments,
            "entries": entries,
            "attachments_by_entry_uid": attachments_by_entry_uid,
            "labels_by_entry_uid": labels_by_entry_uid,
            "all_labels": all_labels,
            "selected_labels": selected_labels,
            "submitted_new_label_names": submitted_new_label_names or [],
            "field_label": "Labels",
            "current_entry_uid": current_entry_uid,
            "form_action": form_action,
            "submit_label": submit_label,
            "remove_attachment_uids_selected": remove_attachment_uids_selected or [],
            "errors": errors or {},
            "form_error": form_error or ("Please fix the highlighted fields." if errors else None),
            "return_next": return_next,
            "cancel_url": return_next or path_for(request, "vendor_detail", vendor_uid=vendor["vendor_uid"]),
        },
    )
    response.status_code = status_code
    return response


@router.get("/entries/new")
def entry_vendor_picker(request: Request):
    vendor_rows = list_entry_vendor_picker_rows(include_archived=False)

    return render_template(
        request,
        "entry_vendor_picker.html",
        {
            "breadcrumbs": [
                {"label": "Home", "url": path_for(request, "read_root")},
                {"label": "New Entry", "url": None},
            ],
            "vendors": vendor_rows,
        },
    )


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
        form_action=path_for(request, "create_vendor_entry", vendor_uid=vendor_uid),
        submit_label="Save Entry",
    )


@router.get("/attachments/{attachment_uid}")
def attachment_download(attachment_uid: str):
    attachment = get_attachment_by_uid(attachment_uid)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    abs_path = resolve_attachment_disk_path(str(attachment["attachment_relative_path"]))
    if abs_path is None or not abs_path.is_file():
        raise HTTPException(status_code=404, detail="Attachment file not found")

    return FileResponse(
        path=abs_path,
        media_type=attachment["attachment_mime_type"] or "application/octet-stream",
        filename=attachment["attachment_original_filename"],
    )


@router.get("/entry/{entry_uid}/edit")
def entry_edit_form(request: Request, entry_uid: str, next: str | None = None):
    entry = get_entry_by_uid(entry_uid)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    vendor = get_vendor_by_uid(entry["vendor_uid"])
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    return_next = _safe_internal_return_target(next)

    return _render_entry_form(
        request,
        mode="edit",
        vendor=vendor,
        entry=dict(entry),
        selected_labels=get_entry_labels_by_uid(entry_uid),
        current_entry_uid=entry_uid,
        form_action=path_for(request, "entry_edit_submit", entry_uid=entry_uid),
        submit_label="Save Entry Changes",
        return_next=return_next,
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
    next: str = Form(""),
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

    return_next = _safe_internal_return_target(next)

    all_labels = list_labels()
    selected_labels, normalized_new_label_names = _select_labels_for_form(
        all_labels,
        label_uids or [],
        new_label_names or [],
    )
    submitted_entry = {
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
            form_action=path_for(request, "entry_edit_submit", entry_uid=entry_uid),
            submit_label="Save Entry Changes",
            remove_attachment_uids_selected=selected_remove_attachment_uids,
            errors=errors,
            return_next=return_next,
            status_code=400,
        )

    now = utc_now_iso()
    try:
        update_entry_by_uid(
            entry_uid=entry_uid,
            entry_title=normalize_optional_text(entry_title),
            entry_interaction_at=clean_entry_interaction_at,
            entry_body_text=normalize_optional_text(entry_body_text),
            entry_rep_name=normalize_optional_text(entry_rep_name),
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
            form_action=path_for(request, "entry_edit_submit", entry_uid=entry_uid),
            submit_label="Save Entry Changes",
            remove_attachment_uids_selected=selected_remove_attachment_uids,
            form_error=str(exc),
            return_next=return_next,
            status_code=400,
        )

    resolved_label_ids = resolve_submitted_labels(
        label_uids=label_uids or [],
        new_label_names=new_label_names or [],
        actor=actor,
        now=now,
    )
    replace_entry_labels_by_uid(entry_uid, resolved_label_ids)

    for attachment_uid in set(remove_attachment_uids or []):
        delete_entry_attachment_by_uid(attachment_uid)

    try:
        store_attachment_uploads_for_entry_uid(entry_uid, new_attachments, actor=actor, max_upload_bytes=MAX_UPLOAD_BYTES)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    redirect_target = return_next or path_for(request, "vendor_detail", vendor_uid=entry["vendor_uid"])
    return RedirectResponse(url=redirect_target, status_code=303)


@router.post("/entry/{entry_uid}/delete")
def entry_delete(request: Request, entry_uid: str, next: str | None = None):
    return_next = _safe_internal_return_target(next)

    try:
        vendor_uid = delete_entry_by_uid(entry_uid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if vendor_uid is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    redirect_target = return_next or path_for(request, "vendor_detail", vendor_uid=vendor_uid)
    return RedirectResponse(url=redirect_target, status_code=303)


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
        return RedirectResponse(url=path_for(request, "vendor_detail", vendor_uid=vendor_uid), status_code=303)

    if errors:
        return _render_entry_form(
            request,
            mode="create",
            vendor=vendor,
            entry=submitted_entry,
            selected_labels=selected_labels,
            submitted_new_label_names=normalized_new_label_names,
            form_action=path_for(request, "create_vendor_entry", vendor_uid=vendor_uid),
            submit_label="Save Entry",
            errors=errors,
            status_code=400,
        )

    now = utc_now_iso()
    new_entry_uid = make_uid("entry")
    try:
        create_entry_for_vendor_uid(
            vendor_uid=vendor_uid,
            entry_uid=new_entry_uid,
            entry_title=normalize_optional_text(entry_title),
            entry_interaction_at=clean_entry_interaction_at,
            entry_body_text=normalize_optional_text(entry_body_text),
            entry_rep_name=normalize_optional_text(entry_rep_name),
            entry_created_by=actor,
            entry_created_at=now,
            label_uids=label_uids or [],
            new_label_names=new_label_names or [],
            attachments=new_attachments,
            max_upload_bytes=MAX_UPLOAD_BYTES,
        )
    except ValueError as exc:
        return _render_entry_form(
            request,
            mode="create",
            vendor=vendor,
            entry=submitted_entry,
            selected_labels=selected_labels,
            submitted_new_label_names=normalized_new_label_names,
            form_action=path_for(request, "create_vendor_entry", vendor_uid=vendor_uid),
            submit_label="Save Entry",
            form_error=str(exc),
            status_code=400,
        )

    return RedirectResponse(url=path_for(request, "vendor_detail", vendor_uid=vendor_uid), status_code=303)


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
