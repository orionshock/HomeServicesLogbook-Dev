from fastapi import APIRouter, Request

from app.db import (
    count_logbook_entries,
    list_attachments_for_entry_ids,
    list_labels_for_entry_ids,
    list_logbook_entries,
)
from app.routes import path_for, render_template

router = APIRouter()

PAGE_SIZE = 25


@router.get("/logbook")
def logbook_page(request: Request, page: int = 1):
    current_page = max(1, int(page))
    total_entries = count_logbook_entries()
    if total_entries > 0:
        total_pages = (total_entries + PAGE_SIZE - 1) // PAGE_SIZE
        current_page = min(current_page, total_pages)

    entries = list_logbook_entries(current_page, page_size=PAGE_SIZE)

    entry_ids = [int(entry["id"]) for entry in entries]

    attachments_by_entry: dict[int, list] = {}
    for attachment in list_attachments_for_entry_ids(entry_ids):
        attachments_by_entry.setdefault(int(attachment["entry_id"]), []).append(attachment)

    labels_by_entry: dict[int, list] = {}
    for label in list_labels_for_entry_ids(entry_ids):
        labels_by_entry.setdefault(int(label["entry_id"]), []).append(label)

    has_prev = current_page > 1
    has_next = current_page * PAGE_SIZE < total_entries

    return render_template(
        request,
        "logbook.html",
        {
            "breadcrumbs": [
                {"label": "Home", "url": path_for(request, "read_root")},
                {"label": "Logbook", "url": None},
            ],
            "entries": entries,
            "attachments_by_entry": attachments_by_entry,
            "labels_by_entry": labels_by_entry,
            "page": current_page,
            "has_prev": has_prev,
            "has_next": has_next,
        },
    )
