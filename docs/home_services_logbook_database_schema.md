# Home Services Logbook - Database Schema Reference

## Purpose

This document defines the intended SQLite schema for **Home Services
Logbook**.

It serves as both: - a developer reference - guidance for GitHub Copilot
and contributors

The system is a **household services logbook**, not a CRM or ticketing
platform.

Core model:

Vendor -\> Entries -\> Attachments

-   **Vendor**: company/person servicing the home
-   **Entry**: chronological logbook record
-   **Attachment**: file related to an entry

The **entries table is the center of gravity** of the system.

------------------------------------------------------------------------

# Design Principles

### Keep the schema simple

Prefer: - a few tables - clear relationships - readable SQL

Avoid: - premature normalization - unnecessary join tables - complicated
abstraction layers

### SQLite first

The project is designed around SQLite.

Schema choices should: - work cleanly with SQLite - remain portable if
migration ever occurs

### Internal IDs vs Public IDs

Every major object has:

  Purpose                      Field
  ---------------------------- ---------------------
  Internal database identity   integer primary key
  Public reference             readable UID

Examples:

-   vendors.id

-   vendors.vendor_uid

-   entries.id

-   entries.entry_uid

Public UIDs are used in URLs.

### Files stored on disk

Uploaded files are **not stored as SQLite BLOBs**.

Instead: - files stored on disk - metadata stored in SQLite

### Most fields optional

The system is a household record tool, not a strict data-entry system.

Most fields should remain optional.

### JSON metadata allowed

SQLite TEXT fields may store JSON for optional metadata.

Use JSON for: - sparse optional fields - experimental metadata - future
expansion

Do not store core relational data in JSON.

------------------------------------------------------------------------

# Core Tables

## vendors

Purpose: - reference sheet for a vendor

Examples:

-   ISP
-   Electric utility
-   HVAC contractor
-   Plumber
-   Appliance repair
-   Insurance provider

Recommended schema:

CREATE TABLE vendors ( id INTEGER PRIMARY KEY, vendor_uid TEXT UNIQUE
NOT NULL, name TEXT NOT NULL, category TEXT, account_number TEXT,
name_on_account TEXT, portal_url TEXT, portal_username TEXT,
phone_on_file TEXT, security_pin TEXT, service_location TEXT,
vendor_notes TEXT, details_json TEXT, created_at TEXT NOT NULL,
updated_at TEXT, archived_at TEXT );

### Key fields

vendor_uid\
Readable unique identifier used in URLs.

Example:

cox-communications-a19f

category\
Simple optional vendor classification.

Examples: ISP\
Utility\
HVAC\
Plumber\
Electrician

details_json\
Optional JSON blob for flexible metadata.

Example:

{ "contact_numbers":\[ {"label":"Support","value":"800-111-2222"},
{"label":"Billing","value":"800-111-3333"} \], "password_manager":{
"app":"Bitwarden", "entry":"Cox Internet" } }

archived_at\
Non-null value indicates vendor is archived.

Archiving is the preferred user-facing lifecycle action; deletion should be avoided in normal use.

------------------------------------------------------------------------

## entries

Purpose: - chronological logbook history - central record of events

Examples of entries:

-   support call note
-   technician visit
-   document upload
-   estimate
-   billing dispute

Recommended schema:

CREATE TABLE entries ( id INTEGER PRIMARY KEY, entry_uid TEXT UNIQUE NOT
NULL, vendor_id INTEGER NOT NULL, entry_type TEXT NOT NULL DEFAULT
'note', body_text TEXT, vendor_reference TEXT, rep_name TEXT, extra_json
TEXT, created_at TEXT NOT NULL, created_by TEXT, updated_at TEXT,
updated_by TEXT, archived_at TEXT, FOREIGN KEY (vendor_id) REFERENCES
vendors(id) );

### Important fields

entry_uid\
Public identifier for entries.

Recommended format:

YYYYMMDD-HHMMSS-hash

Example:

20260311-164233-a84f19

vendor_reference\
Vendor provided reference such as:

case number\
work order\
invoice number

rep_name\
Name of the human contact involved.

extra_json\
Flexible metadata for future expansion.

### Entry Philosophy

Entries behave like logbook records.

Typical workflow:

create entry\
save entry\
append future updates as new entries

Editing previous entries should be secondary behavior.

------------------------------------------------------------------------

## attachments

Purpose: - metadata for uploaded files - actual files stored on disk

Schema:

CREATE TABLE attachments ( id INTEGER PRIMARY KEY, entry_id INTEGER NOT
NULL, original_filename TEXT NOT NULL, stored_filename TEXT NOT NULL,
relative_path TEXT NOT NULL, mime_type TEXT, file_size INTEGER,
checksum_sha256 TEXT, created_at TEXT NOT NULL, FOREIGN KEY (entry_id)
REFERENCES entries(id) );

### Fields

original_filename\
Original upload filename.

stored_filename\
Safe generated filename.

Example:

20260311-164233-a84f19.pdf

relative_path\
Filesystem path relative to project root.

Example:

uploads/2026/03/20260311-164233-a84f19.pdf

checksum_sha256\
Optional SHA-256 checksum for integrity verification.

------------------------------------------------------------------------

# Recommended Indexes

Vendor lookup

CREATE UNIQUE INDEX idx_vendors_vendor_uid ON vendors (vendor_uid);

Entry lookup

CREATE UNIQUE INDEX idx_entries_entry_uid ON entries (entry_uid);

Vendor timeline

CREATE INDEX idx_entries_vendor_created_at ON entries (vendor_id,
created_at DESC);

Attachment lookup

CREATE INDEX idx_attachments_entry_id ON attachments (entry_id);

------------------------------------------------------------------------

# File Storage Rules

Files are stored outside the database.

Reasons:

-   easier backups
-   simpler inspection
-   avoids database bloat

Recommended filename format:

YYYYMMDD-HHMMSS-hash.ext

Example:

20260311-164233-a84f19.pdf

Recommended path layout:

uploads/YYYY/MM/file.ext

Example:

uploads/2026/03/20260311-164233-a84f19.pdf

------------------------------------------------------------------------

# Calendar Behavior

The system intentionally does not include a full calendar subsystem.

Workflow:

1.  user writes entry
2.  user clicks "Add Calendar Event"
3.  popup collects event details
4.  system generates .ics file
5.  event details appended to note

The note remains the authoritative record.

------------------------------------------------------------------------

# Editing Philosophy

The system is logbook-oriented.

Behavior rules:

-   entries editable but edits visible
-   timeline ordering based on created_at
-   users encouraged to append new entries instead of rewriting history

Future versions may introduce:

-   revision history
-   hash chains
-   tamper-evident logs

These are not part of the initial implementation.

------------------------------------------------------------------------

# Future Possible Tables (Not v1)

Potential later features:

labels\
vendor_labels\
entry_labels\
revision history\
cryptographic verification\
search index tables

These should only be added when justified.

------------------------------------------------------------------------

# Core Schema Philosophy

The system revolves around three ideas:

Vendor\
Entry timeline\
Attachments

Everything else is secondary.

When unsure:

keep schema simple\
preserve timeline clarity\
avoid overengineering
