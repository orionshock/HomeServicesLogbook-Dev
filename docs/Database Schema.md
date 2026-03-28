# Home Services Logbook - Database Schema Reference

## Purpose

This document describes the current SQLite schema used by the app and the way the current code exercises it.

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
- Public UIDs are used in routes and URLs; internal integer IDs are used for relationships.
- Most non-key fields are optional.
- entries remains the center of chronological history.

Layer boundary contract:
- app/routes/* uses public identifiers and orchestrates request/response flow.
- app/db/* owns SQL, transactions, UID <-> PK resolution, and multi-step integrity behavior.
- integer primary keys remain internal to DB modules.
- attachment path and file lifecycle concerns live in app/db/attachments.py.

---

## Current Write Rules In App Logic

Some important behavior is enforced in application code rather than by SQLite constraints alone:

- Entry creation is skipped entirely when the submitted form is completely blank and contains no labels or attachments.
- Archived vendors cannot receive new entries.
- Permanent vendor deletion is only available after the vendor has been archived.
- Entry interaction timestamps must parse as UTC timestamps with offset `00:00`; routes normalize them to ISO 8601 `Z` form before persistence.
- Attachments must include a filename extension and are capped at 10 MB per file by route/runtime validation.
- Attachment downloads and deletions use safe path resolution under `APP_UPLOADS_DIR` to block path traversal.
- Mutating routes populate `*_created_by`, `*_updated_by`, and related timestamp columns from the resolved request actor and current UTC time where the schema supports them.

---

## Schema Lifecycle

- Schema is initialized at startup by app/db/schema.py:init_db.
- init_db creates tables and indexes, then inserts the singleton settings row with id = 1 when missing.
- settings access helpers also self-heal the singleton row if it is missing later.
- Development workflow currently applies schema changes by recreating the SQLite file at APP_DB_PATH.
- Migration/backfill logic is intentionally not included in init_db.

---

## Tables

## vendors

Purpose:
- Canonical vendor/service-provider reference sheet.

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

Current usage notes:
- vendor_uid is the public identifier used in vendor routes.
- vendor_archived_at marks archived vendors.
- vendor_updated_at and vendor_updated_by are written during archive, unarchive, and edit operations.
- vendor_details_json exists for future flexibility and is not currently populated by the main vendor form flow.

## entries

Purpose:
- Chronological logbook records tied to a vendor.

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

Current usage notes:
- entry_uid is the public identifier used in entry edit/delete routes.
- Entries are editable after creation, including labels and attachments.
- Logbook ordering uses COALESCE(entry_interaction_at, entry_created_at).
- entry_extra_json exists for future flexibility and is not currently populated by the form routes.

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

Current usage notes:
- attachment_relative_path is stored with forward slashes.
- Files are persisted under APP_UPLOADS_DIR/YYYY/MM/.
- attachment_original_filename is sanitized metadata, not the raw client filename.
- attachment_stored_filename is an internal, collision-resistant disk filename.
- attachment_checksum_sha256 exists in the schema but is not currently populated by store_attachment_upload.
- Attachment lifecycle behavior (write, safe path resolution, delete file + row coordination) is owned by app/db/attachments.py.

## labels

Purpose:
- Reusable label definitions used for filtering and grouping in the UI.

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

Current usage notes:
- label_name is case-insensitive unique.
- label_color accepts #RRGGBB or #RRGGBBAA values validated in app logic.
- DB helper queries commonly project label_name AS name and label_color AS color for route/template use.

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

Current usage notes:
- Vendor label assignments are replaced wholesale by replace_vendor_labels and replace_vendor_labels_by_uid.

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

Current usage notes:
- Entry label assignments are replaced wholesale by replace_entry_labels and replace_entry_labels_by_uid.
- New labels may be created on demand during label resolution when form submissions include new_label_names.

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
- updated_at uses the UTC timestamp helper.
- updated_by defaults to system during seeding/self-heal.

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
- vendors many <-> many labels through vendor_labels
- entries many <-> many labels through entry_labels
- settings is a singleton table keyed by id = 1

Deletion behavior in current code:
- vendor_labels and entry_labels have ON DELETE CASCADE foreign keys.
- entries and attachments are removed explicitly by DB helper functions during delete_entry_by_uid and delete_vendor_by_uid.
- Attachment files are deleted from disk before related DB rows are removed.

Query behavior in current code:
- Logbook search matches entry_title, entry_body_text, entry_rep_name, vendor_name, and entry label names.
- Vendor list and logbook routes both support showing archived vendors based on a cookie/query preference.
- Labels are organizational metadata and do not replace timeline data in entries.
- Vendor list rows and new-entry vendor picker rows are assembled as route-ready structures with label metadata and search text, while keeping internal PK use inside DB helpers.

Boundary reminder:
- Route-to-DB calls use public identifiers such as vendor_uid, entry_uid, attachment_uid, and label_uid.
- DB modules may use integer IDs internally to execute relational operations.
