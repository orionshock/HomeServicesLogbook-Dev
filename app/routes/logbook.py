from urllib.parse import urlencode

from fastapi import APIRouter, Request

from app.db.entries import count_logbook_entries, list_entry_related_data_by_uids, list_logbook_entries
from app.routes import path_for, render_template
from app.runtime import cookie_path_from_root_path

router = APIRouter()

PAGE_SIZE = 25


@router.get("/logbook")
def logbook_page(request: Request, page: int = 1, show_archived: int | None = None, q: str = ""):
    query_has_preference = "show_archived" in request.query_params
    if query_has_preference:
        include_archived = show_archived == 1
    else:
        include_archived = request.cookies.get("show_archived_vendors") == "1"

    current_q = q.strip()
    search_text = current_q or None

    current_page = max(1, int(page))
    total_entries = count_logbook_entries(
        include_archived_vendors=include_archived,
        search_text=search_text,
    )
    if total_entries > 0:
        total_pages = (total_entries + PAGE_SIZE - 1) // PAGE_SIZE
        current_page = min(current_page, total_pages)

    entries = list_logbook_entries(
        current_page,
        page_size=PAGE_SIZE,
        include_archived_vendors=include_archived,
        search_text=search_text,
    )

    entry_edit_return_target = path_for(request, "logbook_page")
    return_query_params: dict[str, str] = {}
    if current_page > 1:
        return_query_params["page"] = str(current_page)
    if include_archived:
        return_query_params["show_archived"] = "1"
    if current_q:
        return_query_params["q"] = current_q
    if return_query_params:
        entry_edit_return_target = f"{entry_edit_return_target}?{urlencode(return_query_params)}"

    entry_uids = [str(entry["entry_uid"]) for entry in entries]
    related_data = list_entry_related_data_by_uids(entry_uids)
    attachments_by_entry_uid = related_data["attachments_by_entry_uid"]
    labels_by_entry_uid = related_data["labels_by_entry_uid"]

    has_prev = current_page > 1
    has_next = current_page * PAGE_SIZE < total_entries

    response = render_template(
        request,
        "logbook.html",
        {
            "breadcrumbs": [
                {"label": "Home", "url": path_for(request, "read_root")},
                {"label": "Logbook", "url": None},
            ],
            "entries": entries,
            "attachments_by_entry_uid": attachments_by_entry_uid,
            "labels_by_entry_uid": labels_by_entry_uid,
            "page": current_page,
            "has_prev": has_prev,
            "has_next": has_next,
            "show_archived": include_archived,
            "q": current_q,
            "entry_edit_return_target": entry_edit_return_target,
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
