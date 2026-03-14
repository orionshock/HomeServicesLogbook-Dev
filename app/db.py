import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "logbook.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
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
                updated_at      TEXT,
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
                entry_id          INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename   TEXT NOT NULL,
                relative_path     TEXT NOT NULL,
                mime_type         TEXT,
                file_size         INTEGER,
                checksum_sha256   TEXT,
                created_at        TEXT NOT NULL,
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
        """)
