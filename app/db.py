import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent.parent / "data" / "logbook.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        # Dev mode: schema changes are applied by recreating data/logbook.db.
        # Do not add migration/backfill logic here.
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS vendors (
                id              INTEGER PRIMARY KEY,
                vendor_uid      TEXT UNIQUE NOT NULL,
                name            TEXT NOT NULL,
                category        TEXT,
                account_number  TEXT,
                name_on_account TEXT,
                portal_url      TEXT,
                portal_username TEXT,
                phone_on_file   TEXT,
                security_pin    TEXT,
                service_location TEXT,
                vendor_notes    TEXT,
                details_json    TEXT,
                created_at      TEXT NOT NULL,
                created_by      TEXT,
                updated_at      TEXT,
                updated_by      TEXT,
                archived_at     TEXT
            );

            CREATE TABLE IF NOT EXISTS entries (
                id               INTEGER PRIMARY KEY,
                entry_uid        TEXT UNIQUE NOT NULL,
                vendor_id        INTEGER NOT NULL,
                entry_type       TEXT NOT NULL DEFAULT 'note',
                body_text        TEXT,
                vendor_reference TEXT,
                rep_name         TEXT,
                extra_json       TEXT,
                created_at       TEXT NOT NULL,
                created_by       TEXT,
                updated_at       TEXT,
                updated_by       TEXT,
                archived_at      TEXT,
                FOREIGN KEY (vendor_id) REFERENCES vendors(id)
            );

            CREATE TABLE IF NOT EXISTS attachments (
                id                INTEGER PRIMARY KEY,
                attachment_uid    TEXT NOT NULL UNIQUE,
                entry_id          INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename   TEXT NOT NULL,
                relative_path     TEXT NOT NULL,
                mime_type         TEXT,
                file_size         INTEGER,
                checksum_sha256   TEXT,
                created_at        TEXT NOT NULL,
                created_by        TEXT,
                FOREIGN KEY (entry_id) REFERENCES entries(id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_vendors_vendor_uid
                ON vendors (vendor_uid);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_entries_entry_uid
                ON entries (entry_uid);

            CREATE INDEX IF NOT EXISTS idx_entries_vendor_created_at
                ON entries (vendor_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_attachments_entry_id
                ON attachments (entry_id);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_attachments_attachment_uid
                ON attachments (attachment_uid);
        """)


# ---------------------------------------------------------------------------
# Vendor helpers
# ---------------------------------------------------------------------------

def get_vendor_by_uid(vendor_uid: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM vendors WHERE vendor_uid = ?",
            (vendor_uid,),
        ).fetchone()


def list_vendors(include_archived: bool = False) -> list[sqlite3.Row]:
    with get_connection() as conn:
        if include_archived:
            return conn.execute(
                "SELECT * FROM vendors ORDER BY archived_at IS NOT NULL, name"
            ).fetchall()
        return conn.execute(
            "SELECT * FROM vendors WHERE archived_at IS NULL ORDER BY name"
        ).fetchall()


def create_vendor(
    vendor_uid: str,
    name: str,
    category: str | None,
    account_number: str | None,
    portal_url: str | None,
    vendor_notes: str | None,
    created_at: str,
    created_by: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO vendors (
                vendor_uid, name, category, account_number,
                portal_url, vendor_notes, created_at, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (vendor_uid, name, category, account_number, portal_url, vendor_notes, created_at, created_by),
        )


def update_vendor_by_uid(
    vendor_uid: str,
    name: str,
    category: str | None,
    account_number: str | None,
    name_on_account: str | None,
    portal_url: str | None,
    portal_username: str | None,
    phone_on_file: str | None,
    security_pin: str | None,
    service_location: str | None,
    vendor_notes: str | None,
    updated_at: str,
    updated_by: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE vendors
            SET
                name = ?,
                category = ?,
                account_number = ?,
                name_on_account = ?,
                portal_url = ?,
                portal_username = ?,
                phone_on_file = ?,
                security_pin = ?,
                service_location = ?,
                vendor_notes = ?,
                updated_at = ?,
                updated_by = ?
            WHERE vendor_uid = ?
            """,
            (
                name, category, account_number, name_on_account,
                portal_url, portal_username, phone_on_file, security_pin,
                service_location, vendor_notes, updated_at, updated_by,
                vendor_uid,
            ),
        )


def archive_vendor_by_uid(vendor_uid: str, archived_at: str, updated_by: str) -> bool:
    """Returns False if the vendor does not exist."""
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT id FROM vendors WHERE vendor_uid = ?",
            (vendor_uid,),
        ).fetchone()
        if exists is None:
            return False
        conn.execute(
            """
            UPDATE vendors
            SET archived_at = ?, updated_at = ?, updated_by = ?
            WHERE vendor_uid = ?
            """,
            (archived_at, archived_at, updated_by, vendor_uid),
        )
        return True


def unarchive_vendor_by_uid(vendor_uid: str, updated_at: str, updated_by: str) -> bool:
    """Returns False if the vendor does not exist."""
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT id FROM vendors WHERE vendor_uid = ?",
            (vendor_uid,),
        ).fetchone()
        if exists is None:
            return False
        conn.execute(
            """
            UPDATE vendors
            SET archived_at = NULL, updated_at = ?, updated_by = ?
            WHERE vendor_uid = ?
            """,
            (updated_at, updated_by, vendor_uid),
        )
        return True


# ---------------------------------------------------------------------------
# Entry helpers
# ---------------------------------------------------------------------------

def list_entries_for_vendor(vendor_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM entries
            WHERE vendor_id = ?
              AND archived_at IS NULL
            ORDER BY created_at DESC, id DESC
            """,
            (vendor_id,),
        ).fetchall()


def get_entry_by_uid(entry_uid: str) -> sqlite3.Row | None:
    """Returns the entry row joined with vendor_uid and vendor name."""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT e.*, v.vendor_uid, v.name AS vendor_name
            FROM entries e
            JOIN vendors v ON v.id = e.vendor_id
            WHERE e.entry_uid = ?
            """,
            (entry_uid,),
        ).fetchone()


def create_entry(
    entry_uid: str,
    vendor_id: int,
    body_text: str | None,
    vendor_reference: str | None,
    rep_name: str | None,
    created_by: str,
    created_at: str,
) -> int:
    """Inserts an entry and returns the new row id."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO entries (
                entry_uid, vendor_id, body_text, vendor_reference,
                rep_name, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (entry_uid, vendor_id, body_text, vendor_reference, rep_name, created_by, created_at),
        )
        return cursor.lastrowid


def update_entry_by_uid(
    entry_uid: str,
    body_text: str | None,
    vendor_reference: str | None,
    rep_name: str | None,
    updated_at: str,
    updated_by: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE entries
            SET
                body_text = ?,
                vendor_reference = ?,
                rep_name = ?,
                updated_at = ?,
                updated_by = ?
            WHERE entry_uid = ?
            """,
            (body_text, vendor_reference, rep_name, updated_at, updated_by, entry_uid),
        )


# ---------------------------------------------------------------------------
# Attachment helpers
# ---------------------------------------------------------------------------

def get_attachment_by_uid(attachment_uid: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT attachment_uid, original_filename, relative_path, mime_type
            FROM attachments
            WHERE attachment_uid = ?
            """,
            (attachment_uid,),
        ).fetchone()


def list_attachments_for_entry_ids(entry_ids: list[int]) -> list[sqlite3.Row]:
    if not entry_ids:
        return []
    with get_connection() as conn:
        placeholders = ",".join("?" for _ in entry_ids)
        return conn.execute(
            f"""
            SELECT attachment_uid, entry_id, original_filename
            FROM attachments
            WHERE entry_id IN ({placeholders})
            ORDER BY id ASC
            """,
            tuple(entry_ids),
        ).fetchall()


def create_attachment(
    attachment_uid: str,
    entry_id: int,
    original_filename: str,
    stored_filename: str,
    relative_path: str,
    mime_type: str | None,
    file_size: int,
    created_by: str,
    created_at: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO attachments (
                attachment_uid, entry_id, original_filename, stored_filename,
                relative_path, mime_type, file_size, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attachment_uid, entry_id, original_filename, stored_filename,
                relative_path, mime_type, file_size, created_by, created_at,
            ),
        )
