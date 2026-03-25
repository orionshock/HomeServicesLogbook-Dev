"""Entry persistence queries and form-context aggregation helpers."""

import sqlite3

from .connection import get_connection
from app.utils import normalize_optional_text


def _build_logbook_where_clause(
    include_archived_vendors: bool,
    search_text: str | None,
) -> tuple[str, list[str]]:
    """Build the optional WHERE clause and parameters for logbook listing queries."""
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
    """List entries for a vendor primary key, newest first."""
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


def list_entries_for_vendor_uid(vendor_uid: str) -> list[sqlite3.Row]:
    """List entries for a vendor using UID instead of PK."""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT e.*, v.vendor_uid, v.vendor_name
            FROM entries e
            JOIN vendors v ON v.id = e.vendor_id
            WHERE v.vendor_uid = ?
            ORDER BY e.entry_created_at DESC, e.id DESC
            """,
            (vendor_uid,),
        ).fetchall()


def list_logbook_entries(
    page: int,
    page_size: int = 25,
    include_archived_vendors: bool = False,
    search_text: str | None = None,
) -> list[sqlite3.Row]:
    """Return paginated logbook entries with optional archive/search filters."""
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
    """Count logbook entries for the current filter settings."""
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


def create_entry_for_vendor_uid(
    vendor_uid: str,
    entry_uid: str,
    entry_title: str | None,
    entry_interaction_at: str | None,
    entry_body_text: str | None,
    entry_rep_name: str | None,
    entry_created_by: str,
    entry_created_at: str,
    label_uids: list[str],
    new_label_names: list[str],
    attachments,
    max_upload_bytes: int,
) -> dict[str, str]:
    """
    Create an entry for a vendor UID and apply labels/uploads without exposing PKs.

    Returns only route-facing UID data.
    """
    from .attachments import store_attachment_uploads
    from .labels import replace_entry_labels, resolve_submitted_labels
    from .vendors import get_vendor_by_uid

    vendor = get_vendor_by_uid(vendor_uid)
    if vendor is None:
        raise ValueError("Vendor not found")

    entry_id = create_entry(
        entry_uid=entry_uid,
        vendor_id=int(vendor["id"]),
        entry_title=entry_title,
        entry_interaction_at=entry_interaction_at,
        entry_body_text=entry_body_text,
        entry_rep_name=entry_rep_name,
        entry_created_by=entry_created_by,
        entry_created_at=entry_created_at,
    )

    resolved_label_ids = resolve_submitted_labels(
        label_uids=label_uids,
        new_label_names=new_label_names,
        actor=entry_created_by,
        now=entry_created_at,
    )
    replace_entry_labels(entry_id, resolved_label_ids)

    store_attachment_uploads(
        attachments,
        entry_id=entry_id,
        actor=entry_created_by,
        max_upload_bytes=max_upload_bytes,
    )

    return {
        "entry_uid": entry_uid,
        "vendor_uid": str(vendor["vendor_uid"]),
    }


def update_entry_by_uid(
    entry_uid: str,
    entry_title: str | None,
    entry_interaction_at: str | None,
    entry_body_text: str | None,
    entry_rep_name: str | None,
    entry_updated_at: str,
    entry_updated_by: str,
) -> None:
    """Update an entry by public UID."""
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

    delete_attachment_files_for_entry(entry_id)

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
    Return UID-shaped form context for vendor entry pages.

    The helper resolves internal PK relationships and keeps routes free of DB-key joins.
    Raises ValueError when the vendor UID does not exist.
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

    entries = list_entries_for_vendor(vendor_id)
    entry_ids = [int(e["id"]) for e in entries]

    entry_id_to_uid = {int(e["id"]): str(e["entry_uid"]) for e in entries}

    attachments_by_entry_uid: dict[str, list] = {}
    if entry_ids:
        for attachment in list_attachments_for_entry_ids(entry_ids):
            entry_id = int(attachment["entry_id"])
            entry_uid = entry_id_to_uid.get(entry_id)
            if entry_uid is None:
                continue
            attachments_by_entry_uid.setdefault(entry_uid, []).append(attachment)

    labels_by_entry_uid: dict[str, list] = {}
    if entry_ids:
        for label in list_labels_for_entry_ids(entry_ids):
            entry_id = int(label["entry_id"])
            entry_uid = entry_id_to_uid.get(entry_id)
            if entry_uid is None:
                continue
            labels_by_entry_uid.setdefault(entry_uid, []).append(label)

    for entry_id in entry_ids:
        entry_uid = entry_id_to_uid.get(entry_id)
        if entry_uid is None or entry_uid in labels_by_entry_uid:
            continue
        labels_by_entry_uid[entry_uid] = list_labels_for_entry_id(entry_id)

    vendor_labels = list_labels_for_vendor_id(vendor_id)

    all_labels = list_labels()

    entry_attachments = []
    if entry_uid_to_edit:
        for entry in entries:
            if str(entry["entry_uid"]) == entry_uid_to_edit:
                entry_attachments = list_attachments_for_entry_id(int(entry["id"]))
                break

    return {
        "vendor": vendor,
        "entries": entries,
        "attachments_by_entry_uid": attachments_by_entry_uid,
        "labels_by_entry_uid": labels_by_entry_uid,
        "vendor_labels": vendor_labels,
        "all_labels": all_labels,
        "entry_attachments": entry_attachments,
    }


def list_entry_related_data_by_uids(entry_uids: list[str]) -> dict[str, dict[str, list[sqlite3.Row]]]:
    """
    Return attachment and label collections keyed by entry UID.

    Internal PK joins stay in the DB layer.
    """
    clean_entry_uids = [str(entry_uid).strip() for entry_uid in entry_uids if str(entry_uid).strip()]
    unique_entry_uids = list(dict.fromkeys(clean_entry_uids))
    if not unique_entry_uids:
        return {
            "attachments_by_entry_uid": {},
            "labels_by_entry_uid": {},
        }

    placeholders = ", ".join("?" for _ in unique_entry_uids)

    with get_connection() as conn:
        attachment_rows = conn.execute(
            f"""
            SELECT
                e.entry_uid,
                a.attachment_uid,
                a.attachment_original_filename
            FROM attachments a
            JOIN entries e ON e.id = a.entry_id
            WHERE e.entry_uid IN ({placeholders})
            ORDER BY a.id ASC
            """,
            unique_entry_uids,
        ).fetchall()

        label_rows = conn.execute(
            f"""
            SELECT
                e.entry_uid,
                l.label_uid,
                l.label_name AS name,
                l.label_color AS color
            FROM entry_labels el
            JOIN entries e ON e.id = el.entry_id
            JOIN labels l ON l.id = el.label_id
            WHERE e.entry_uid IN ({placeholders})
            ORDER BY e.entry_uid, l.label_name COLLATE NOCASE
            """,
            unique_entry_uids,
        ).fetchall()

    attachments_by_entry_uid: dict[str, list[sqlite3.Row]] = {}
    for row in attachment_rows:
        entry_uid = str(row["entry_uid"])
        attachments_by_entry_uid.setdefault(entry_uid, []).append(row)

    labels_by_entry_uid: dict[str, list[sqlite3.Row]] = {}
    for row in label_rows:
        entry_uid = str(row["entry_uid"])
        labels_by_entry_uid.setdefault(entry_uid, []).append(row)

    return {
        "attachments_by_entry_uid": attachments_by_entry_uid,
        "labels_by_entry_uid": labels_by_entry_uid,
    }