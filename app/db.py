import sqlite3
from pathlib import Path

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
                id                     INTEGER PRIMARY KEY,
                vendor_uid             TEXT UNIQUE NOT NULL,
                vendor_name            TEXT NOT NULL,
                vendor_label           TEXT,
                vendor_account_number  TEXT,
                vendor_portal_url      TEXT,
                vendor_portal_username TEXT,
                vendor_phone_number    TEXT,
                vendor_address         TEXT,
                vendor_notes           TEXT,
                vendor_details_json    TEXT,
                vendor_created_at      TEXT NOT NULL,
                vendor_created_by      TEXT,
                vendor_updated_at      TEXT,
                vendor_updated_by      TEXT,
                vendor_archived_at     TEXT
            );

            CREATE TABLE IF NOT EXISTS entries (
                id                   INTEGER PRIMARY KEY,
                entry_uid            TEXT UNIQUE NOT NULL,
                vendor_id            INTEGER NOT NULL,
                entry_title          TEXT,
                entry_interaction_at TEXT,
                entry_body_text      TEXT,
                entry_rep_name       TEXT,
                entry_extra_json     TEXT,
                entry_created_at     TEXT NOT NULL,
                entry_created_by     TEXT,
                entry_updated_at     TEXT,
                entry_updated_by     TEXT,
                entry_archived_at    TEXT,
                FOREIGN KEY (vendor_id) REFERENCES vendors(id)
            );

            CREATE TABLE IF NOT EXISTS attachments (
                id                            INTEGER PRIMARY KEY,
                attachment_uid                TEXT NOT NULL UNIQUE,
                entry_id                      INTEGER NOT NULL,
                attachment_original_filename  TEXT NOT NULL,
                attachment_stored_filename    TEXT NOT NULL,
                attachment_relative_path      TEXT NOT NULL,
                attachment_mime_type          TEXT,
                attachment_file_size          INTEGER,
                attachment_checksum_sha256    TEXT,
                attachment_created_at         TEXT NOT NULL,
                attachment_created_by         TEXT,
                FOREIGN KEY (entry_id) REFERENCES entries(id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_vendors_vendor_uid
                ON vendors (vendor_uid);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_entries_entry_uid
                ON entries (entry_uid);

            CREATE INDEX IF NOT EXISTS idx_entries_vendor_created_at
                ON entries (vendor_id, entry_created_at DESC);

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
                "SELECT * FROM vendors ORDER BY vendor_archived_at IS NOT NULL, vendor_name"
            ).fetchall()
        return conn.execute(
            "SELECT * FROM vendors WHERE vendor_archived_at IS NULL ORDER BY vendor_name"
        ).fetchall()


def create_vendor(
    vendor_uid: str,
    vendor_name: str,
    vendor_label: str | None,
    vendor_account_number: str | None,
    vendor_portal_url: str | None,
    vendor_portal_username: str | None,
    vendor_phone_number: str | None,
    vendor_address: str | None,
    vendor_notes: str | None,
    vendor_created_at: str,
    vendor_created_by: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO vendors (
                vendor_uid, vendor_name, vendor_label, vendor_account_number,
                vendor_portal_url, vendor_portal_username,
                vendor_phone_number, vendor_address,
                vendor_notes, vendor_created_at, vendor_created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                vendor_uid,
                vendor_name,
                vendor_label,
                vendor_account_number,
                vendor_portal_url,
                vendor_portal_username,
                vendor_phone_number,
                vendor_address,
                vendor_notes,
                vendor_created_at,
                vendor_created_by,
            ),
        )


def update_vendor_by_uid(
    vendor_uid: str,
    vendor_name: str,
    vendor_label: str | None,
    vendor_account_number: str | None,
    vendor_portal_url: str | None,
    vendor_portal_username: str | None,
    vendor_phone_number: str | None,
    vendor_address: str | None,
    vendor_notes: str | None,
    vendor_updated_at: str,
    vendor_updated_by: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE vendors
            SET
                vendor_name = ?,
                vendor_label = ?,
                vendor_account_number = ?,
                vendor_portal_url = ?,
                vendor_portal_username = ?,
                vendor_phone_number = ?,
                vendor_address = ?,
                vendor_notes = ?,
                vendor_updated_at = ?,
                vendor_updated_by = ?
            WHERE vendor_uid = ?
            """,
            (
                vendor_name,
                vendor_label,
                vendor_account_number,
                vendor_portal_url,
                vendor_portal_username,
                vendor_phone_number,
                vendor_address,
                vendor_notes,
                vendor_updated_at,
                vendor_updated_by,
                vendor_uid,
            ),
        )


def archive_vendor_by_uid(vendor_uid: str, vendor_archived_at: str, vendor_updated_by: str) -> bool:
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
            SET vendor_archived_at = ?, vendor_updated_at = ?, vendor_updated_by = ?
            WHERE vendor_uid = ?
            """,
            (vendor_archived_at, vendor_archived_at, vendor_updated_by, vendor_uid),
        )
        return True


def unarchive_vendor_by_uid(vendor_uid: str, vendor_updated_at: str, vendor_updated_by: str) -> bool:
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
            SET vendor_archived_at = NULL, vendor_updated_at = ?, vendor_updated_by = ?
            WHERE vendor_uid = ?
            """,
            (vendor_updated_at, vendor_updated_by, vendor_uid),
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
              AND entry_archived_at IS NULL
            ORDER BY entry_created_at DESC, id DESC
            """,
            (vendor_id,),
        ).fetchall()


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


# ---------------------------------------------------------------------------
# Attachment helpers
# ---------------------------------------------------------------------------

def get_attachment_by_uid(attachment_uid: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT attachment_uid, entry_id, attachment_original_filename,
                   attachment_relative_path, attachment_mime_type
            FROM attachments
            WHERE attachment_uid = ?
            """,
            (attachment_uid,),
        ).fetchone()


def list_attachments_for_entry_id(entry_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, attachment_uid, entry_id, attachment_original_filename,
                   attachment_relative_path, attachment_mime_type,
                   attachment_file_size, attachment_created_at
            FROM attachments
            WHERE entry_id = ?
            ORDER BY id ASC
            """,
            (entry_id,),
        ).fetchall()


# NOTE:
# This dynamically generates "?, ?, ?" placeholders for a parameterized IN clause.
# Only placeholder tokens are interpolated, never user input.
# The actual values are still bound safely through sqlite parameters.
def list_attachments_for_entry_ids(entry_ids: list[int]) -> list[sqlite3.Row]:
    if not entry_ids:
        return []
    with get_connection() as conn:
        param_placeholders = ",".join("?" for _ in entry_ids)
        return conn.execute(
            f"""
            SELECT attachment_uid, entry_id, attachment_original_filename
            FROM attachments
            WHERE entry_id IN ({param_placeholders})
            ORDER BY id ASC
            """,
            tuple(entry_ids),
        ).fetchall()


def create_attachment(
    attachment_uid: str,
    entry_id: int,
    attachment_original_filename: str,
    attachment_stored_filename: str,
    attachment_relative_path: str,
    attachment_mime_type: str | None,
    attachment_file_size: int,
    attachment_created_by: str,
    attachment_created_at: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO attachments (
                attachment_uid, entry_id, attachment_original_filename,
                attachment_stored_filename, attachment_relative_path,
                attachment_mime_type, attachment_file_size,
                attachment_created_by, attachment_created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attachment_uid,
                entry_id,
                attachment_original_filename,
                attachment_stored_filename,
                attachment_relative_path,
                attachment_mime_type,
                attachment_file_size,
                attachment_created_by,
                attachment_created_at,
            ),
        )


def delete_attachment_by_uid_for_entry(entry_id: int, attachment_uid: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        attachment = conn.execute(
            """
            SELECT id, attachment_uid, entry_id, attachment_original_filename,
                   attachment_relative_path, attachment_mime_type
            FROM attachments
            WHERE entry_id = ? AND attachment_uid = ?
            """,
            (entry_id, attachment_uid),
        ).fetchone()
        if attachment is None:
            return None

        conn.execute(
            "DELETE FROM attachments WHERE id = ?",
            (attachment["id"],),
        )
        return attachment
