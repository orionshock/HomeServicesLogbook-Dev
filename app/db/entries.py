import sqlite3

from .connection import get_connection
from app.utils import normalize_optional_text


def _build_logbook_where_clause(
    include_archived_vendors: bool,
    search_text: str | None,
) -> tuple[str, list[str]]:
    clauses: list[str] = []
    params: list[str] = []

    if not include_archived_vendors:
        clauses.append("v.vendor_archived_at IS NULL")

    normalized_search_text = normalize_optional_text(search_text)
    if normalized_search_text:
        like_value = f"%{normalized_search_text}%"
        clauses.append(
            """
            (
                e.entry_title LIKE ?
                OR e.entry_body_text LIKE ?
                OR e.entry_rep_name LIKE ?
                OR v.vendor_name LIKE ?
                OR EXISTS (
                    SELECT 1
                    FROM entry_labels el
                    JOIN labels l ON l.id = el.label_id
                    WHERE el.entry_id = e.id
                      AND l.label_name LIKE ?
                )
            )
            """.strip()
        )
        params.extend([like_value, like_value, like_value, like_value, like_value])

    if not clauses:
        return "", params

    return f"WHERE {' AND '.join(clauses)}", params


def list_entries_for_vendor(vendor_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM entries
            WHERE vendor_id = ?
            ORDER BY entry_created_at DESC, id DESC
            """,
            (vendor_id,),
        ).fetchall()


def list_logbook_entries(
    page: int,
    page_size: int = 25,
    include_archived_vendors: bool = False,
    search_text: str | None = None,
) -> list[sqlite3.Row]:
    safe_page = max(1, int(page))
    safe_page_size = max(1, int(page_size))
    offset = (safe_page - 1) * safe_page_size

    with get_connection() as conn:
        where_clause, where_params = _build_logbook_where_clause(
            include_archived_vendors=include_archived_vendors,
            search_text=search_text,
        )
        return conn.execute(
            f"""
            SELECT
                e.*,
                v.vendor_uid,
                v.vendor_name,
                v.vendor_archived_at,
                COALESCE(e.entry_interaction_at, e.entry_created_at) AS entry_timeline_at
            FROM entries e
            JOIN vendors v ON v.id = e.vendor_id
            {where_clause}
            ORDER BY COALESCE(e.entry_interaction_at, e.entry_created_at) DESC, e.id DESC
            LIMIT ? OFFSET ?
            """,
            (*where_params, safe_page_size, offset),
        ).fetchall()


def count_logbook_entries(
    include_archived_vendors: bool = False,
    search_text: str | None = None,
) -> int:
    with get_connection() as conn:
        where_clause, where_params = _build_logbook_where_clause(
            include_archived_vendors=include_archived_vendors,
            search_text=search_text,
        )
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM entries e
            JOIN vendors v ON v.id = e.vendor_id
            {where_clause}
            """,
            where_params,
        ).fetchone()
        return int(row["total"]) if row else 0


def get_entry_by_uid(entry_uid: str) -> sqlite3.Row | None:
    """Returns the entry row joined with vendor_uid and vendor name."""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT e.*, v.vendor_uid, v.vendor_name
            FROM entries e
            JOIN vendors v ON v.id = e.vendor_id
            WHERE e.entry_uid = ?
            """,
            (entry_uid,),
        ).fetchone()

def create_entry(
    entry_uid: str,
    vendor_id: int,
    entry_title: str | None,
    entry_interaction_at: str | None,
    entry_body_text: str | None,
    entry_rep_name: str | None,
    entry_created_by: str,
    entry_created_at: str,
) -> int:
    """Inserts an entry and returns the new row id."""
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO entries (
                    entry_uid, vendor_id, entry_title, entry_interaction_at,
                    entry_body_text, entry_rep_name, entry_created_by, entry_created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_uid,
                    vendor_id,
                    entry_title,
                    entry_interaction_at,
                    entry_body_text,
                    entry_rep_name,
                    entry_created_by,
                    entry_created_at,
                ),
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError as exc:
            raise ValueError("Entry could not be saved due to invalid data") from exc


def update_entry_by_uid(
    entry_uid: str,
    entry_title: str | None,
    entry_interaction_at: str | None,
    entry_body_text: str | None,
    entry_rep_name: str | None,
    entry_updated_at: str,
    entry_updated_by: str,
) -> None:
    with get_connection() as conn:
        try:
            conn.execute(
                """
                UPDATE entries
                SET
                    entry_title = ?,
                    entry_interaction_at = ?,
                    entry_body_text = ?,
                    entry_rep_name = ?,
                    entry_updated_at = ?,
                    entry_updated_by = ?
                WHERE entry_uid = ?
                """,
                (
                    entry_title,
                    entry_interaction_at,
                    entry_body_text,
                    entry_rep_name,
                    entry_updated_at,
                    entry_updated_by,
                    entry_uid,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Entry could not be updated due to invalid data") from exc


def delete_entry_by_uid(entry_uid: str) -> str | None:
    """
    Deletes an entry by UID along with its attachment files, attachment rows,
    and entry-label join rows.

    - Attachment files are removed first via db/attachments.
    - DB rows are only deleted after all file deletions succeed.
    - Returns the vendor_uid of the deleted entry (for redirect), or None if not found.
    - Raises ValueError if an attachment path is invalid.
    - Raises OSError if a file exists but cannot be deleted.
    """
    from .attachments import delete_attachment_files_for_entry

    entry = get_entry_by_uid(entry_uid)
    if entry is None:
        return None

    entry_id = int(entry["id"])
    vendor_uid = str(entry["vendor_uid"])

    # Validate and delete physical files first. Raises on failure.
    delete_attachment_files_for_entry(entry_id)

    # Only reach here if all file deletions succeeded.
    with get_connection() as conn:
        conn.execute("DELETE FROM attachments WHERE entry_id = ?", (entry_id,))
        conn.execute("DELETE FROM entry_labels WHERE entry_id = ?", (entry_id,))
        conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))

    return vendor_uid


def get_vendor_entry_form_context(
    vendor_uid: str,
    entry_uid_to_edit: str | None = None,
) -> dict:
    """
    Get complete context for entry form (new or edit) without exposing PKs to routes.
    
    Internally resolves UIDs to PKs and aggregates all necessary data for form rendering.
    Returns UID-shaped data that routes can consume directly.
    
    Args:
        vendor_uid: UID of the vendor
        entry_uid_to_edit: Optional UID of entry being edited (none for new entry form)
    
    Returns:
        {
            "vendor": vendor_row,
            "entries": [entry_rows],  # all entries for vendor, ordered DESC by created_at
            "attachments_by_entry": dict[int, list],  # keyed by entry id (for template)
            "labels_by_entry": dict[int, list],  # keyed by entry id (for template)
            "vendor_labels": [label_rows],
            "all_labels": [label_rows],
            "entry_attachments": [attachment_rows],  # attachments for current entry (if editing)
        }
    
    Raises ValueError if vendor not found.
    """
    from .attachments import list_attachments_for_entry_id, list_attachments_for_entry_ids
    from .labels import (
        list_labels,
        list_labels_for_vendor_id,
        list_labels_for_entry_id,
        list_labels_for_entry_ids,
    )
    from .vendors import get_vendor_by_uid

    vendor = get_vendor_by_uid(vendor_uid)
    if vendor is None:
        raise ValueError(f"Vendor not found: {vendor_uid}")

    vendor_id = int(vendor["id"])

    # Get all entries for this vendor
    entries = list_entries_for_vendor(vendor_id)
    entry_ids = [int(e["id"]) for e in entries]

    # Build map from entry_id to entry_uid for looking up attachments later
    entry_id_to_uid = {int(e["id"]): str(e["entry_uid"]) for e in entries}

    # Get all attachments for all entries, organized by entry_id (for template compatibility)
    attachments_by_entry: dict[int, list] = {}
    if entry_ids:
        for attachment in list_attachments_for_entry_ids(entry_ids):
            entry_id = int(attachment["entry_id"])
            attachments_by_entry.setdefault(entry_id, []).append(attachment)

    # Get all labels for entries, organized by entry_id (for template compatibility)
    labels_by_entry: dict[int, list] = {}
    if entry_ids:
        for label in list_labels_for_entry_ids(entry_ids):
            entry_id = int(label["entry_id"])
            labels_by_entry.setdefault(entry_id, []).append(label)

    # Also populate labels_by_entry for each entry by id if not already fetched
    for entry_id in entry_ids:
        if entry_id not in labels_by_entry:
            labels_by_entry[entry_id] = list_labels_for_entry_id(entry_id)

    # Get labels for the vendor
    vendor_labels = list_labels_for_vendor_id(vendor_id)

    # Get all labels
    all_labels = list_labels()

    # Get attachments for the entry being edited (if applicable)
    entry_attachments = []
    if entry_uid_to_edit:
        for entry in entries:
            if str(entry["entry_uid"]) == entry_uid_to_edit:
                entry_attachments = list_attachments_for_entry_id(int(entry["id"]))
                break

    return {
        "vendor": vendor,
        "entries": entries,
        "attachments_by_entry": attachments_by_entry,
        "labels_by_entry": labels_by_entry,
        "vendor_labels": vendor_labels,
        "all_labels": all_labels,
        "entry_attachments": entry_attachments,
    }