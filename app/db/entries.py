import sqlite3

from .connection import get_connection


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


def list_logbook_entries(page: int, page_size: int = 25, include_archived_vendors: bool = False) -> list[sqlite3.Row]:
    safe_page = max(1, int(page))
    safe_page_size = max(1, int(page_size))
    offset = (safe_page - 1) * safe_page_size

    with get_connection() as conn:
        where_clause = "" if include_archived_vendors else "WHERE v.vendor_archived_at IS NULL"
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
            (safe_page_size, offset),
        ).fetchall()


def count_logbook_entries(include_archived_vendors: bool = False) -> int:
    with get_connection() as conn:
        where_clause = "" if include_archived_vendors else "WHERE v.vendor_archived_at IS NULL"
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM entries e
            JOIN vendors v ON v.id = e.vendor_id
            {where_clause}
            """
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