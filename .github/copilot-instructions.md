# Home Services Logbook - Copilot Instructions

## Project overview
This project is a small self-hosted web app called **Home Services Logbook**.

Purpose:
- Keep a household logbook for vendors and service providers related to a home.
- Examples: ISP, electric company, water utility, plumber, HVAC, electrician, roofer, appliance repair, insurance, HOA, landscaper.
- The app is a **digital logbook and document archive**, not a CRM, ticketing system, or task platform.

Core mental model:
- **Vendor** = the company or person who services the home
- **Entry** = a chronological note in the vendor history
- **Attachment** = a file related to an entry
- Everything important should be organized around the vendor timeline

## Product principles
- Favor simplicity over cleverness.
- Favor boring, maintainable code over abstraction-heavy code.
- Favor server-rendered HTML over frontend framework complexity.
- The app should feel like a **digital household filing cabinet + logbook**.
- Most user data fields should be optional.
- The UX should encourage adding new entries instead of rewriting old history.
- Calendar support is export-only, not a full calendar system.
- Passwords are not stored in this app.

## Tech stack
Use these defaults unless explicitly told otherwise:
- Python
- FastAPI
- Jinja templates
- SQLite
- Local filesystem for uploaded files
- Minimal JavaScript only when necessary

Do not introduce React, Vue, Angular, Node build systems, ORMs, or extra infrastructure unless explicitly requested.

## Architecture rules
- Keep the architecture simple and local-first.
- Files are stored on disk; SQLite stores metadata only.
- Use internal integer primary keys for relational integrity.
- Also use readable public UIDs for URLs:
  - vendor_uid
  - entry_uid
- Prefer a small number of tables with clear purposes.

Current core model:
- vendors
- entries
- attachments

Conceptual model:
- Vendor -> many Entries
- Entry -> many Attachments

## Database guidance
Prefer SQLite-friendly, maintainable schema design.

Expected schema direction:
- `vendors` table for vendor reference data
- `entries` table for the chronological logbook
- `attachments` table for file metadata

Important:
- `entries` is the center of gravity of the app
- keep timeline/history data primarily in `entries`
- optional JSON blob fields are acceptable for future flexibility
- do not over-normalize early

Use parameterized SQL only.
Never build SQL queries with string interpolation.

## Security rules
Treat all external input as untrusted:
- form fields
- URL params
- uploaded filenames
- headers
- future Home Assistant identity headers

Required practices:
- parameterized SQL only
- escape output in templates
- never trust uploaded filenames
- generate safe stored filenames
- never use user input directly in file paths
- whitelist any dynamic sorting or filtering options
- do not silently fetch or execute user-supplied URLs

## File upload rules
- Store uploaded files on disk, not in SQLite BLOBs.
- Store only metadata in the database.
- Preserve original filename as metadata only.
- Generate a separate safe internal storage filename.
- Prefer a naming scheme like:
  - `YYYYMMDD-HHMMSS-shorthash.ext`
- Use relative paths where possible.

## UX rules
The main vendor page should have:
- vendor reference details at the top
- a large note/entry box
- buttons for:
  - Save Entry
  - Add Calendar Event
  - Attach Document
- a vendor history/timeline visible on the side

Behavior rules:
- Saving an entry should return the user to a blank entry area for the same vendor.
- This is intentional and should encourage chronological logging.
- Editing previous notes should be possible, but not the primary path.
- Prefer “append new entry” behavior over “rewrite history” behavior.

## Calendar rules
Calendar support is intentionally lightweight.
Do not build a persistent calendar subsystem unless explicitly requested.

Current design:
- User writes a note
- User can click "Add Calendar Event"
- A popup collects:
  - title
  - date
  - optional time
  - description
- The app generates an `.ics` file on demand
- The event details are appended into the in-progress note
- The note remains the source record

Do not create a full calendar sync system.

## Vendor data rules
The vendor page is a reference sheet for real-world interactions.

Typical useful vendor info may include:
- vendor name
- category
- name on account
- account number
- contact numbers
- bill-to address
- phone on file
- security PIN
- service location
- portal URL
- portal username
- password manager app name
- password manager entry name
- vendor notes

Most of these should remain optional.
It is acceptable to keep some flexible vendor data in JSON rather than separate columns.

## Coding style
- Write clear, direct, readable Python.
- Prefer small functions.
- Avoid unnecessary classes unless they improve clarity.
- Use descriptive variable names.
- Add comments only when they help explain intent.
- Do not over-engineer.
- Do not add frameworks or patterns “just in case.”

## Scope control
This project is now in active development.

Prioritize:
1. vendor records
2. entry creation
3. vendor history timeline
4. document attachment
5. simple ICS export

Still defer until later unless explicitly requested:
- advanced labeling/tagging
- multi-database support
- complex auth
- Home Assistant integration details
- signature verification
- legal/tamper-evident features
- deep search/indexing
- complex settings systems

## When generating code
When suggesting code changes:
- preserve the current architecture
- prefer incremental edits over rewrites
- explain major file additions briefly
- do not introduce unnecessary dependencies
- assume this project may later become a Home Assistant add-on, but do not optimize for that prematurely