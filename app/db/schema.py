from .connection import get_connection


def init_db() -> None:
    with get_connection() as conn:
        # Dev mode: schema changes are applied by recreating data/logbook.db.
        # Do not add migration/backfill logic here.
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS vendors (
                id                     INTEGER PRIMARY KEY,
                vendor_uid             TEXT UNIQUE NOT NULL,
                vendor_name            TEXT NOT NULL CHECK (length(trim(vendor_name)) > 0),
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

            CREATE TABLE IF NOT EXISTS labels (
                id          INTEGER PRIMARY KEY,
                label_uid   TEXT UNIQUE NOT NULL,
                label_name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
                label_color       TEXT,
                label_created_at  TEXT NOT NULL,
                label_created_by  TEXT,
                label_updated_at  TEXT,
                label_updated_by  TEXT
            );

            CREATE TABLE IF NOT EXISTS vendor_labels (
                vendor_id INTEGER NOT NULL,
                label_id  INTEGER NOT NULL,
                PRIMARY KEY (vendor_id, label_id),
                FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE CASCADE,
                FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS entry_labels (
                entry_id INTEGER NOT NULL,
                label_id INTEGER NOT NULL,
                PRIMARY KEY (entry_id, label_id),
                FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE,
                FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE CASCADE
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

            CREATE UNIQUE INDEX IF NOT EXISTS idx_labels_label_uid
                ON labels (label_uid);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_labels_name_nocase
                ON labels (label_name COLLATE NOCASE);

            CREATE INDEX IF NOT EXISTS idx_vendor_labels_label_id
                ON vendor_labels (label_id);

            CREATE INDEX IF NOT EXISTS idx_entry_labels_label_id
                ON entry_labels (label_id);
        """)