import string
from urllib.parse import urlparse

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.db import (
    archive_vendor_by_uid,
    create_vendor,
    get_vendor_by_uid,
    list_attachments_for_entry_ids,
    list_entries_for_vendor,
    list_labels,
    list_labels_for_entry_id,
    list_labels_for_vendor_id,
    list_labels_for_vendor_ids,
    list_vendors,
    replace_vendor_labels,
    resolve_submitted_labels,
    unarchive_vendor_by_uid,
    update_vendor_by_uid,
)
from app.routes import path_for, render_template
from app.utils import make_uid, normalize_required_text, utc_now_iso

router = APIRouter()

AZ_SECTION_KEYS = [*string.ascii_uppercase, "0..9", "#"]


def normalize_portal_url(value: str) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None

    if any(ch.isspace() for ch in normalized):
        raise ValueError("Portal URL must not contain spaces")

    # Allow common user input like "example.com" by defaulting to HTTPS.
    if "://" not in normalized:
        normalized = f"https://{normalized}"

    parsed = urlparse(normalized)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Portal URL must start with http:// or https://")

    if not parsed.netloc or parsed.hostname is None:
        raise ValueError("Portal URL must include a valid host")

    return normalized


def _normalize_optional_text(value: str) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def _vendor_name_sort_key(vendor: dict) -> str:
    return str(vendor["vendor_name"]).casefold()


def _az_section_key(vendor_name: str) -> str:
    first_character = (vendor_name or "").strip()[:1]
    if not first_character:
        return "#"

    if first_character.isdigit():
        return "0..9"

    uppercase_character = first_character.upper()
    if uppercase_character in string.ascii_uppercase:
        return uppercase_character

    return "#"


def _build_vendor_listing_rows(vendors: list) -> list[dict]:
    labels_by_vendor_id: dict[int, list[dict]] = {}
    vendor_ids = [int(vendor["id"]) for vendor in vendors]

    for row in list_labels_for_vendor_ids(vendor_ids):
        labels_by_vendor_id.setdefault(int(row["vendor_id"]), []).append(
            {
                "id": int(row["id"]),
                "label_uid": row["label_uid"],
                "name": row["name"],
                "color": row["color"],
            }
        )

    listing_rows: list[dict] = []
    for vendor in vendors:
        vendor_id = int(vendor["id"])
        labels = labels_by_vendor_id.get(vendor_id, [])
        label_names = [label["name"] for label in labels]
        listing_rows.append(
            {
                "id": vendor_id,
                "vendor_uid": vendor["vendor_uid"],
                "vendor_name": vendor["vendor_name"],
                "vendor_archived_at": vendor["vendor_archived_at"],
                "labels": labels,
                "label_names": label_names,
                "search_text": " ".join([vendor["vendor_name"], *label_names]).strip(),
            }
        )

    return sorted(listing_rows, key=_vendor_name_sort_key)


def _build_az_sections(vendors: list[dict]) -> list[dict]:
    grouped_vendors = {section_key: [] for section_key in AZ_SECTION_KEYS}

    for vendor in vendors:
        grouped_vendors[_az_section_key(vendor["vendor_name"])].append(vendor)

    return [
        {
            "key": section_key,
            "title": section_key,
            "vendors": grouped_vendors[section_key],
        }
        for section_key in AZ_SECTION_KEYS
        if grouped_vendors[section_key]
    ]


def _build_category_sections(vendors: list[dict]) -> list[dict]:
    grouped_sections: dict[str, dict] = {}
    uncategorized_vendors: list[dict] = []

    for vendor in vendors:
        if vendor["labels"]:
            for label in vendor["labels"]:
                section = grouped_sections.setdefault(
                    str(label["label_uid"]),
                    {
                        "key": str(label["label_uid"]),
                        "title": label["name"],
                        "vendors": [],
                    },
                )
                section["vendors"].append(vendor)
        else:
            uncategorized_vendors.append(vendor)

    ordered_sections = sorted(grouped_sections.values(), key=lambda section: section["title"].casefold())
    if uncategorized_vendors:
        ordered_sections.append(
            {
                "key": "uncategorized",
                "title": "Uncategorized",
                "vendors": uncategorized_vendors,
            }
        )

    return ordered_sections


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
        normalized_name = " ".join((raw_name or "").split()).strip()
        if not normalized_name:
            continue
        name_key = normalized_name.lower()
        if name_key in seen_name_keys:
            continue
        seen_name_keys.add(name_key)
        normalized_new_names.append(normalized_name)

    return selected_labels, normalized_new_names


def _render_vendor_form(
    request: Request,
    *,
    is_edit: bool,
    form_action: str,
    submit_label: str,
    vendor: dict | None,
    selected_labels: list,
    submitted_new_label_names: list[str] | None = None,
    errors: dict[str, str] | None = None,
    status_code: int = 200,
):
    page_title = "Edit" if is_edit else "New Vendor"
    breadcrumbs = [
        {"label": "Home", "url": path_for(request, "read_root")},
        {"label": "Vendors", "url": path_for(request, "vendor_list")},
    ]
    if is_edit and vendor is not None:
        breadcrumbs.append({"label": vendor["vendor_name"], "url": path_for(request, "vendor_detail", vendor_uid=vendor["vendor_uid"])})
    breadcrumbs.append({"label": page_title, "url": None})

    response = render_template(
        request,
        "vendor_form.html",
        {
            "breadcrumbs": breadcrumbs,
            "vendor": vendor,
            "all_labels": list_labels(),
            "selected_labels": selected_labels,
            "submitted_new_label_names": submitted_new_label_names or [],
            "field_label": "Categories",
            "is_edit": is_edit,
            "form_action": form_action,
            "submit_label": submit_label,
            "errors": errors or {},
            "form_error": "Please fix the highlighted fields." if errors else None,
        },
    )
    response.status_code = status_code
    return response


@router.get("/vendors/new")
def vendor_new_form(request: Request):
    return _render_vendor_form(
        request,
        is_edit=False,
        form_action=path_for(request, "vendor_new_submit"),
        submit_label="Save Vendor",
        vendor=None,
        selected_labels=[],
    )


@router.post("/vendors/new")
def vendor_new_submit(
    request: Request,
    vendor_name: str = Form(""),
    vendor_account_number: str = Form(""),
    vendor_portal_url: str = Form(""),
    vendor_portal_username: str = Form(""),
    vendor_phone_number: str = Form(""),
    vendor_address: str = Form(""),
    vendor_notes: str = Form(""),
    label_uids: list[str] | None = Form(None),
    new_label_names: list[str] | None = Form(None),
):
    actor = request.state.current_actor["actor_id"]
    all_labels = list_labels()
    selected_labels, normalized_new_label_names = _select_labels_for_form(
        all_labels,
        label_uids or [],
        new_label_names or [],
    )
    submitted_vendor = {
        "vendor_name": vendor_name,
        "vendor_account_number": vendor_account_number,
        "vendor_portal_url": vendor_portal_url,
        "vendor_portal_username": vendor_portal_username,
        "vendor_phone_number": vendor_phone_number,
        "vendor_address": vendor_address,
        "vendor_notes": vendor_notes,
    }
    errors: dict[str, str] = {}

    try:
        clean_vendor_name = normalize_required_text(vendor_name, "Vendor name")
    except ValueError as exc:
        errors["vendor_name"] = str(exc)
        clean_vendor_name = ""

    try:
        clean_vendor_portal_url = normalize_portal_url(vendor_portal_url)
    except ValueError as exc:
        errors["vendor_portal_url"] = str(exc)
        clean_vendor_portal_url = None

    if errors:
        return _render_vendor_form(
            request,
            is_edit=False,
            form_action=path_for(request, "vendor_new_submit"),
            submit_label="Save Vendor",
            vendor=submitted_vendor,
            selected_labels=selected_labels,
            submitted_new_label_names=normalized_new_label_names,
            errors=errors,
            status_code=400,
        )

    vendor_uid = make_uid("vendor", name=clean_vendor_name)
    now = utc_now_iso()
    try:
        create_vendor(
            vendor_uid=vendor_uid,
            vendor_name=clean_vendor_name,
            vendor_account_number=_normalize_optional_text(vendor_account_number),
            vendor_portal_url=clean_vendor_portal_url,
            vendor_portal_username=_normalize_optional_text(vendor_portal_username),
            vendor_phone_number=_normalize_optional_text(vendor_phone_number),
            vendor_address=_normalize_optional_text(vendor_address),
            vendor_notes=_normalize_optional_text(vendor_notes),
            vendor_created_at=now,
            vendor_created_by=actor,
        )
    except ValueError as exc:
        errors["vendor_name"] = str(exc)
        return _render_vendor_form(
            request,
            is_edit=False,
            form_action=path_for(request, "vendor_new_submit"),
            submit_label="Save Vendor",
            vendor=submitted_vendor,
            selected_labels=selected_labels,
            submitted_new_label_names=normalized_new_label_names,
            errors=errors,
            status_code=400,
        )

    created_vendor = get_vendor_by_uid(vendor_uid)
    if created_vendor is None:
        raise HTTPException(status_code=500, detail="Vendor was not created")

    resolved_label_ids = resolve_submitted_labels(
        label_uids=label_uids or [],
        new_label_names=new_label_names or [],
        actor=actor,
        now=now,
    )
    replace_vendor_labels(created_vendor["id"], resolved_label_ids)

    return RedirectResponse(url=path_for(request, "vendor_detail", vendor_uid=vendor_uid), status_code=303)


@router.get("/vendors")
def vendor_list(request: Request, show_archived: int | None = None):
    query_has_preference = "show_archived" in request.query_params
    if query_has_preference:
        include_archived = show_archived == 1
    else:
        include_archived = request.cookies.get("show_archived_vendors") == "1"

    vendors = list_vendors(include_archived)
    listing_rows = _build_vendor_listing_rows(vendors)
    response = render_template(
        request,
        "vendor_listing.html",
        {
            "breadcrumbs": [
                {"label": "Home", "url": path_for(request, "read_root")},
                {"label": "Vendors", "url": None},
            ],
            "vendors": listing_rows,
            "az_sections": _build_az_sections(listing_rows),
            "category_sections": _build_category_sections(listing_rows),
            "show_archived": include_archived,
        },
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


@router.post("/vendor/{vendor_uid}/archive")
def vendor_archive(request: Request, vendor_uid: str):
    actor = request.state.current_actor["actor_id"]
    now = utc_now_iso()
    found = archive_vendor_by_uid(vendor_uid, vendor_archived_at=now, vendor_updated_by=actor)
    if not found:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return RedirectResponse(url=path_for(request, "vendor_list"), status_code=303)


@router.post("/vendor/{vendor_uid}/unarchive")
def vendor_unarchive(request: Request, vendor_uid: str):
    actor = request.state.current_actor["actor_id"]
    now = utc_now_iso()
    found = unarchive_vendor_by_uid(vendor_uid, vendor_updated_at=now, vendor_updated_by=actor)
    if not found:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return RedirectResponse(url=path_for(request, "vendor_detail", vendor_uid=vendor_uid), status_code=303)


@router.get("/vendor/{vendor_uid}")
def vendor_detail(request: Request, vendor_uid: str):
    vendor = get_vendor_by_uid(vendor_uid)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    entries = list_entries_for_vendor(vendor["id"])
    vendor_labels = list_labels_for_vendor_id(vendor["id"])
    attachments_by_entry: dict[int, list] = {}
    labels_by_entry: dict[int, list] = {}
    for item in list_attachments_for_entry_ids([e["id"] for e in entries]):
        attachments_by_entry.setdefault(item["entry_id"], []).append(item)
    for item in entries:
        labels_by_entry[item["id"]] = list_labels_for_entry_id(item["id"])

    return render_template(
        request,
        "vendor_detail.html",
        {
            "breadcrumbs": [
                {"label": "Home", "url": path_for(request, "read_root")},
                {"label": "Vendors", "url": path_for(request, "vendor_list")},
                {"label": vendor["vendor_name"], "url": None},
            ],
            "vendor": vendor,
            "vendor_labels": vendor_labels,
            "entries": entries,
            "attachments_by_entry": attachments_by_entry,
            "labels_by_entry": labels_by_entry,
        },
    )


@router.get("/vendor/{vendor_uid}/edit")
def vendor_edit_form(request: Request, vendor_uid: str):
    vendor = get_vendor_by_uid(vendor_uid)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    return _render_vendor_form(
        request,
        is_edit=True,
        form_action=path_for(request, "vendor_edit_submit", vendor_uid=vendor_uid),
        submit_label="Save Changes",
        vendor=dict(vendor),
        selected_labels=list_labels_for_vendor_id(vendor["id"]),
    )


@router.post("/vendor/{vendor_uid}/edit")
def vendor_edit_submit(
    request: Request,
    vendor_uid: str,
    vendor_name: str = Form(""),
    vendor_account_number: str = Form(""),
    vendor_portal_url: str = Form(""),
    vendor_portal_username: str = Form(""),
    vendor_phone_number: str = Form(""),
    vendor_address: str = Form(""),
    vendor_notes: str = Form(""),
    label_uids: list[str] | None = Form(None),
    new_label_names: list[str] | None = Form(None),
):
    actor = request.state.current_actor["actor_id"]
    vendor = get_vendor_by_uid(vendor_uid)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    all_labels = list_labels()
    selected_labels, normalized_new_label_names = _select_labels_for_form(
        all_labels,
        label_uids or [],
        new_label_names or [],
    )
    submitted_vendor = {
        "vendor_uid": vendor_uid,
        "vendor_name": vendor_name,
        "vendor_account_number": vendor_account_number,
        "vendor_portal_url": vendor_portal_url,
        "vendor_portal_username": vendor_portal_username,
        "vendor_phone_number": vendor_phone_number,
        "vendor_address": vendor_address,
        "vendor_notes": vendor_notes,
    }
    errors: dict[str, str] = {}

    try:
        clean_vendor_name = normalize_required_text(vendor_name, "Vendor name")
    except ValueError as exc:
        errors["vendor_name"] = str(exc)
        clean_vendor_name = ""

    try:
        clean_vendor_portal_url = normalize_portal_url(vendor_portal_url)
    except ValueError as exc:
        errors["vendor_portal_url"] = str(exc)
        clean_vendor_portal_url = None

    if errors:
        return _render_vendor_form(
            request,
            is_edit=True,
            form_action=path_for(request, "vendor_edit_submit", vendor_uid=vendor_uid),
            submit_label="Save Changes",
            vendor=submitted_vendor,
            selected_labels=selected_labels,
            submitted_new_label_names=normalized_new_label_names,
            errors=errors,
            status_code=400,
        )

    now = utc_now_iso()
    try:
        update_vendor_by_uid(
            vendor_uid=vendor_uid,
            vendor_name=clean_vendor_name,
            vendor_account_number=_normalize_optional_text(vendor_account_number),
            vendor_portal_url=clean_vendor_portal_url,
            vendor_portal_username=_normalize_optional_text(vendor_portal_username),
            vendor_phone_number=_normalize_optional_text(vendor_phone_number),
            vendor_address=_normalize_optional_text(vendor_address),
            vendor_notes=_normalize_optional_text(vendor_notes),
            vendor_updated_at=now,
            vendor_updated_by=actor,
        )
    except ValueError as exc:
        errors["vendor_name"] = str(exc)
        return _render_vendor_form(
            request,
            is_edit=True,
            form_action=path_for(request, "vendor_edit_submit", vendor_uid=vendor_uid),
            submit_label="Save Changes",
            vendor=submitted_vendor,
            selected_labels=selected_labels,
            submitted_new_label_names=normalized_new_label_names,
            errors=errors,
            status_code=400,
        )

    resolved_label_ids = resolve_submitted_labels(
        label_uids=label_uids or [],
        new_label_names=new_label_names or [],
        actor=actor,
        now=now,
    )
    replace_vendor_labels(vendor["id"], resolved_label_ids)

    return RedirectResponse(url=path_for(request, "vendor_detail", vendor_uid=vendor_uid), status_code=303)
