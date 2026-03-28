import string
from urllib.parse import urlparse

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.db import (
    archive_vendor_by_uid,
    create_vendor,
    delete_vendor_by_uid,
    get_vendor_by_uid,
    get_vendor_delete_context,
    list_entries_for_vendor_uid,
    list_entry_related_data_by_uids,
    list_labels,
    list_labels_for_vendor_uid,
    list_vendor_listing_rows,
    replace_vendor_labels_by_uid,
    unarchive_vendor_by_uid,
    update_vendor_by_uid,
)
from app.routes import path_for, render_template
from app.runtime import cookie_path_from_root_path
from app.utils import make_uid, normalize_optional_text, normalize_required_text, utc_now_iso

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
            vendor_account_number=normalize_optional_text(vendor_account_number),
            vendor_portal_url=clean_vendor_portal_url,
            vendor_portal_username=normalize_optional_text(vendor_portal_username),
            vendor_phone_number=normalize_optional_text(vendor_phone_number),
            vendor_address=normalize_optional_text(vendor_address),
            vendor_notes=normalize_optional_text(vendor_notes),
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

    replace_vendor_labels_by_uid(
        vendor_uid=vendor_uid,
        label_uids=label_uids or [],
        new_label_names=new_label_names or [],
        actor=actor,
        now=now,
    )

    return RedirectResponse(url=path_for(request, "vendor_detail", vendor_uid=vendor_uid), status_code=303)


@router.get("/vendors")
def vendor_list(request: Request, show_archived: int | None = None):
    query_has_preference = "show_archived" in request.query_params
    if query_has_preference:
        include_archived = show_archived == 1
    else:
        include_archived = request.cookies.get("show_archived_vendors") == "1"

    listing_rows = list_vendor_listing_rows(include_archived)
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
            path=cookie_path_from_root_path(
                (getattr(request.state, "effective_root_path", "") or "").strip()
            ),
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
def vendor_detail(request: Request, vendor_uid: str, delete_blocked: int | None = None):
    vendor = get_vendor_by_uid(vendor_uid)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    entries = list_entries_for_vendor_uid(vendor_uid)
    vendor_labels = list_labels_for_vendor_uid(vendor_uid)
    entry_uids = [str(entry["entry_uid"]) for entry in entries]
    related_data = list_entry_related_data_by_uids(entry_uids)
    attachments_by_entry_uid = related_data["attachments_by_entry_uid"]
    labels_by_entry_uid = related_data["labels_by_entry_uid"]

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
            "attachments_by_entry_uid": attachments_by_entry_uid,
            "labels_by_entry_uid": labels_by_entry_uid,
            "delete_blocked": bool(delete_blocked),
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
        selected_labels=list_labels_for_vendor_uid(vendor_uid),
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
            vendor_account_number=normalize_optional_text(vendor_account_number),
            vendor_portal_url=clean_vendor_portal_url,
            vendor_portal_username=normalize_optional_text(vendor_portal_username),
            vendor_phone_number=normalize_optional_text(vendor_phone_number),
            vendor_address=normalize_optional_text(vendor_address),
            vendor_notes=normalize_optional_text(vendor_notes),
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

    replace_vendor_labels_by_uid(
        vendor_uid=vendor_uid,
        label_uids=label_uids or [],
        new_label_names=new_label_names or [],
        actor=actor,
        now=now,
    )

    return RedirectResponse(url=path_for(request, "vendor_detail", vendor_uid=vendor_uid), status_code=303)


@router.get("/vendor/{vendor_uid}/delete")
def vendor_delete_page(request: Request, vendor_uid: str, page_error: str | None = None):
    context = get_vendor_delete_context(vendor_uid)
    if context is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if not context["vendor_archived_at"]:
        # Active vendors may not be deleted; redirect back to the detail page.
        return RedirectResponse(
            url=path_for(request, "vendor_detail", vendor_uid=vendor_uid)
            + "?delete_blocked=1",
            status_code=303,
        )

    return render_template(
        request,
        "vendor_delete.html",
        {
            "breadcrumbs": [
                {"label": "Home", "url": path_for(request, "read_root")},
                {"label": "Vendors", "url": path_for(request, "vendor_list")},
                {
                    "label": context["vendor_name"],
                    "url": path_for(request, "vendor_detail", vendor_uid=vendor_uid),
                },
                {"label": "Delete Vendor", "url": None},
            ],
            "context": context,
            "page_error": page_error,
        },
    )


@router.post("/vendor/{vendor_uid}/delete/confirm")
def vendor_delete_confirm(request: Request, vendor_uid: str):
    context = get_vendor_delete_context(vendor_uid)
    if context is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if not context["vendor_archived_at"]:
        return RedirectResponse(
            url=path_for(request, "vendor_detail", vendor_uid=vendor_uid)
            + "?delete_blocked=1",
            status_code=303,
        )

    try:
        delete_vendor_by_uid(vendor_uid)
    except (ValueError, OSError) as exc:
        response = render_template(
            request,
            "vendor_delete.html",
            {
                "breadcrumbs": [
                    {"label": "Home", "url": path_for(request, "read_root")},
                    {"label": "Vendors", "url": path_for(request, "vendor_list")},
                    {
                        "label": context["vendor_name"],
                        "url": path_for(request, "vendor_detail", vendor_uid=vendor_uid),
                    },
                    {"label": "Delete Vendor", "url": None},
                ],
                "context": context,
                "page_error": str(exc),
            },
        )
        response.status_code = 400
        return response

    # Redirect to vendors list showing archived vendors, since the deleted vendor was archived.
    return RedirectResponse(
        url=path_for(request, "vendor_list") + "?show_archived=1",
        status_code=303,
    )
