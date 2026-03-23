# Home Services Logbook - Database Schema Reference

## Purpose

This document describes the current SQLite schema used by the app.

Source of truth:
- app/db/schema.py
- app/db/*.py query helpers

The data model remains timeline-first:

Vendor -> Entries -> Attachments

Labels are optional organizational metadata that can be attached to both vendors and entries.

---

## Design Principles

- SQLite-first, no ORM.
- Parameterized SQL only.
- Files stored on disk; DB stores file metadata.
- Public UIDs are used in URLs, internal integer IDs are used for relationships.
- Most non-key fields are optional.
- entries is the center of chronological history.

---

## Schema Lifecycle

- Schema is initialized at startup by app/db/schema.py:init_db.
- During initialization, the singleton settings row is inserted with id = 1 when missing.
- Development workflow applies schema changes by recreating the SQLite file at APP_DB_PATH (default: data/logbook.db).
- Migration/backfill logic is intentionally not included in init_db.

---

## Tables

## vendors

Purpose:
- Canonical record for a service provider/company reference sheet.

```sql
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
```

Notes:
- vendor_uid is the public identifier used in vendor URLs.
- vendor_archived_at marks archived vendors.

## entries

Purpose:
- Timeline records tied to a vendor.

```sql
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
```

Notes:
- entry_uid is the public identifier used in entry edit URLs.
- Entries are editable after creation (title, interaction timestamp, body text, representative, labels, attachments).
- Vendor archival is supported via vendor_archived_at.

## attachments

Purpose:
- Metadata for uploaded files linked to an entry.

```sql
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
```

Notes:
- attachment_relative_path is stored with forward slashes.
- Files are persisted under APP_UPLOADS_DIR/YYYY/MM/ (default: data/uploads/YYYY/MM/).

## labels

Purpose:
- Reusable label definitions used for filtering/grouping in UI.

```sql
CREATE TABLE IF NOT EXISTS labels (
    id                INTEGER PRIMARY KEY,
    label_uid         TEXT UNIQUE NOT NULL,
    label_name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    label_color       TEXT,
    label_created_at  TEXT NOT NULL,
    label_created_by  TEXT,
    label_updated_at  TEXT,
    label_updated_by  TEXT
);
```

Notes:
- label_name is case-insensitive unique.
- label_color accepts hex values validated in app logic.

## vendor_labels

Purpose:
- Many-to-many link between vendors and labels.

```sql
CREATE TABLE IF NOT EXISTS vendor_labels (
    vendor_id INTEGER NOT NULL,
    label_id  INTEGER NOT NULL,
    PRIMARY KEY (vendor_id, label_id),
    FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE CASCADE,
    FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE CASCADE
);
```

## entry_labels

Purpose:
- Many-to-many link between entries and labels.

```sql
CREATE TABLE IF NOT EXISTS entry_labels (
    entry_id INTEGER NOT NULL,
    label_id INTEGER NOT NULL,
    PRIMARY KEY (entry_id, label_id),
    FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE,
    FOREIGN KEY (label_id) REFERENCES labels(id) ON DELETE CASCADE
);
```

## settings

Purpose:
- Singleton location metadata used on the home page and edited from /settings.

```sql
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY,
    location_name TEXT NOT NULL,
    location_address TEXT NOT NULL DEFAULT '',
    location_description TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL
);
```

Seed behavior:
- Row id = 1 is inserted with defaults when missing.
- Default location_name = Welcome Home.
- Default location_address = empty string.
- Default location_description = See Settings below to change this header.
- updated_at uses app UTC timestamp helper.
- updated_by defaults to system.

---

## Indexes

```sql
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
```

---

## Relationship Summary

- vendors 1 -> many entries
- entries 1 -> many attachments
- vendors many <-> many labels (through vendor_labels)
- entries many <-> many labels (through entry_labels)
- settings is a singleton table keyed by id = 1

Labels are organizational metadata and do not replace timeline data in entries.
