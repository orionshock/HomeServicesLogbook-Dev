# Home Services Logbook - Project Architecture

## Technology Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Web | FastAPI |
| Templates | Jinja2 |
| Database | SQLite |
| Storage | Local filesystem |
| Frontend | Server-rendered HTML + focused vanilla JS |

No frontend framework, no build system, no ORM.

---

## Current Product Surface

Implemented user-facing workflows in the current codebase:

- Home page showing the current location/settings summary.
- Vendor listing with A-Z and category-style grouping plus archived toggle persistence.
- Vendor create, edit, archive, unarchive, and archived-only permanent delete flows.
- Vendor detail pages that combine reference data with the vendor timeline.
- Global new-entry vendor picker.
- Entry create, edit, delete, label assignment, attachment add/remove, and attachment download.
- Global logbook view with pagination, archived-vendor filtering, and free-text search.
- Label administration with inline JSON-backed create, rename, recolor, delete, and suggestion APIs.
- Settings page for the singleton location record.
- Optional actor override and upstream actor support.
- On-demand `.ics` calendar export.

---

## Runtime Flow

```text
Browser Request
  -> FastAPI app (app/main.py)
    -> actor_context_middleware resolves request.state.current_actor
    -> Route module (app/routes/*.py or app/actor.py)
      -> DB helper module (app/db/*.py)
        -> SQLite (APP_DB_PATH, default data/logbook.db)
      -> Jinja template render (templates/*.html) or JSON/file response
  -> HTML, JSON, redirect, or file download response
```

For uploads:
- Files are written to APP_UPLOADS_DIR/YYYY/MM (default: data/uploads/YYYY/MM).
- SQLite stores attachment metadata and the relative upload path.
- Route handlers validate form input and size limits, while app/db/attachments.py owns disk writes and cleanup.

---

## Layer Boundaries (Current Contract)

The app is organized around a route -> DB boundary where public identifiers remain UID-shaped and persistence details stay in app/db.

## Routes Layer (app/routes/* and app/actor.py)

Role:
- Request/response flow and orchestration.
- Works with public identifiers such as vendor_uid, entry_uid, attachment_uid, and label_uid.

Routes handle:
- parsing form, query, path, JSON, and upload input
- validation and normalization of submitted values
- calling DB-layer operation helpers
- redirects, HTTP errors, template rendering, and API/file responses

Routes must not:
- expose integer primary keys
- include SQL
- write or delete attachment files directly
- depend on storage layout details beyond calling DB helpers

## DB Layer (app/db/*)

Role:
- Owns persistence behavior and data integrity.

DB modules handle:
- SQL queries and transactions
- resolving UIDs <-> internal integer IDs
- multi-step delete/update behavior
- attachment file persistence and safe path resolution

DB modules may use integer IDs internally, but route-facing helpers keep public identifiers UID-shaped.

## Attachments Responsibility (app/db/attachments.py)

The attachments module owns attachment persistence across SQLite and the filesystem.

It is responsible for:
- writing uploaded files to APP_UPLOADS_DIR/YYYY/MM
- sanitizing original filenames for metadata
- generating collision-resistant stored filenames
- resolving safe disk paths under APP_UPLOADS_DIR
- deleting file + attachment row behavior together when requested through DB helpers

Route modules interact with attachments through DB functions such as store_attachment_uploads_for_entry_uid, resolve_attachment_disk_path, and delete_entry_attachment_by_uid_for_entry_uid.

## Boundary Rule Summary

- Public identifiers crossing the route <-> DB boundary remain UID-shaped.
- Integer primary keys stay inside DB modules.
- Filesystem concerns stay inside attachment DB helpers, except that routes may return a FileResponse using a safe path returned by resolve_attachment_disk_path.

---

## Current Folder Structure

```text
HomeServicesLogbook/
|-- app/
|   |-- actor.py (actor resolution logic and actor override routes)
|   |-- main.py (FastAPI app setup, middleware, exception handlers, router registration)
|   |-- runtime.py (environment-driven runtime config values and path resolution)
|   |-- utils.py (shared helpers for text normalization, IDs, and timestamps)
|   |-- db/
|   |   |-- connection.py (SQLite connection factory with Row mapping)
|   |   |-- schema.py (schema initialization and default settings seed)
|   |   |-- vendors.py (vendor CRUD, archive/unarchive, delete context, permanent delete)
|   |   |-- entries.py (entry CRUD, logbook listing/counting, form-context aggregation)
|   |   |-- attachments.py (attachment metadata persistence, safe path resolution, upload/delete lifecycle)
|   |   |-- labels.py (label CRUD, search, and vendor/entry label assignment helpers)
|   |   |-- settings.py (singleton settings read/update helpers for id = 1)
|   |   `-- __init__.py (barrel exports for DB helper modules)
|   `-- routes/
|       |-- __init__.py (shared template rendering, path_for helper, MAX_UPLOAD_BYTES)
|       |-- home.py (home route and lifespan initialization)
|       |-- vendors.py (vendor listing, create/edit, archive/unarchive, delete flows)
|       |-- entries.py (entry create/edit/delete routes, attachment downloads, ICS export)
|       |-- logbook.py (global chronological logbook route with pagination and search)
|       |-- labels.py (label admin page plus JSON label management routes)
|       `-- settings.py (settings form GET/POST routes)
|-- templates/
|   |-- 404.html (not-found error view)
|   |-- base.html (shared shell layout, navigation, and script blocks)
|   |-- entry_form.html (entry create/edit workflow page)
|   |-- entry_vendor_picker.html (global new-entry vendor selection page)
|   |-- error.html (generic error view for 4xx/5xx responses)
|   |-- home.html (home dashboard)
|   |-- label_admin.html (label management page)
|   |-- logbook.html (global paginated logbook timeline view)
|   |-- settings.html (location metadata settings form)
|   |-- vendor_delete.html (archived-vendor delete confirmation page)
|   |-- vendor_detail.html (vendor profile and timeline landing page)
|   |-- vendor_form.html (vendor create/edit form)
|   |-- vendor_listing.html (vendor index with A-Z and category views)
|   |-- macros/
|   |   `-- overflow_menu.html (shared overflow action menu macro)
|   `-- partials/
|       |-- actor_control.html (shared actor override control)
|       |-- label_picker.html (shared label picker UI fragment)
|       |-- log_entry_card.html (vendor timeline entry card rendering)
|       |-- logbook_entry_card.html (global logbook entry card rendering)
|       `-- vendor_header_card.html (shared vendor summary/header card)
|-- static/
|   |-- css/
|   |   |-- base.css (theme tokens and foundational typography/colors)
|   |   |-- components.css (shared buttons and reusable component styling)
|   |   |-- entries.css (entry workflow and timeline styles)
|   |   |-- forms.css (input/textarea/form-field styling)
|   |   |-- home.css (home page layout styles)
|   |   |-- labels.css (label management and label-chip styles)
|   |   |-- layout.css (app-shell layout primitives)
|   |   `-- vendors.css (vendor listing/detail styles)
|   `-- js/
|       |-- actor_control.js (actor/user override UI)
|       |-- entry_form.js (entry form interactions, calendar helpers, layout behavior)
|       |-- entry_vendor_picker.js (vendor selection UX for global new-entry flow)
|       |-- external_links.js (marks external links with an icon)
|       |-- label_admin.js (label management inline editing)
|       |-- label_picker.js (label autocomplete and selection)
|       |-- smokeTester.js (dev smoke test and sample data route exerciser)
|       |-- time.js (UTC-to-local time formatting)
|       |-- unsaved_changes.js (form dirty-state detection and navigation warnings)
|       |-- vendor_header_card.js (phone number link formatting)
|       `-- vendors.js (A-Z/category view switching and vendor search)
|-- data/
|   |-- logbook.db (SQLite database file for app data; default APP_DB_PATH)
|   `-- uploads/ (stored uploaded files organized by date folders; default APP_UPLOADS_DIR)
|-- docs/
|   |-- Project Architecture.md (system layout, routes, and composition reference)
|   |-- Database Schema.md (SQLite table/index and lifecycle reference)
|   `-- Style Guide.md (coding/style conventions for contributors and Copilot)
|-- requirements.txt (Python dependency list)
`-- README.md (project overview and quick-start guidance)
```

---

## Runtime Modes

The app supports two root-path modes:

1. Static root path mode
  - `APP_ROOT_PATH` is set once at startup.
  - `FastAPI(..., root_path=APP_ROOT_PATH)` uses that mounted prefix.

2. Upstream forwarded root path mode
  - `USE_UPSTREAM_ROOT_PATH=true`
  - `resolve_effective_root_path()` reads `UPSTREAM_ROOT_PATH_HEADER` on each request.
  - `path_for()` and cookie scoping use the per-request effective root path.

The app also supports two actor identity modes:

1. Default/local actor mode
  - actor falls back to `user`
  - optional cookie-based override is enabled only when `ALLOW_ACTOR_OVERRIDE=true`

2. Trusted upstream actor mode
  - `USE_UPSTREAM_AUTH=true`
  - actor comes from `UPSTREAM_ACTOR_HEADER` unless a local override is allowed and present

Development entry points currently in the repo:

- `docker-compose.yml`
  - builds from the included `Dockerfile`
  - mounts a named volume at `/data`
  - loads additional env vars from `.env`

---

## App Composition

## app/main.py

Responsibilities:
- Creates the FastAPI app with lifespan from app/routes/home.py.
- Applies request-aware root_path via middleware.
- Mounts static files at /static.
- Registers exception handlers:
  - HTTPException -> 404.html or error.html
  - RequestValidationError -> error.html (400)
  - Exception -> error.html (500)
- Adds middleware to attach request.state.current_actor.
- Includes routers:
  - home
  - actor
  - vendors
  - entries
  - logbook
  - labels
  - settings

## app/routes/__init__.py

Shared route utilities:
- BASE_DIR path resolution.
- MAX_UPLOAD_BYTES = 10 MB.
- Jinja template registry.
- path_for helper that respects root_path and avoids duplicate prefixes.
- render_template helper that injects request, url_for, current_actor, and allow_actor_override.

## app/actor.py

Actor and override handling:
- Current actor precedence:
  - actor_override cookie, but only when ALLOW_ACTOR_OVERRIDE is enabled
  - trusted upstream header, when USE_UPSTREAM_AUTH is enabled
  - default actor_id = user
- Async/fetch requests receive JSON responses.
- Non-async requests receive redirects back to the referer or home page.

## app/runtime.py

Environment normalization helpers and runtime constants:
- USE_UPSTREAM_AUTH
- UPSTREAM_ACTOR_HEADER
- USE_UPSTREAM_ROOT_PATH
- UPSTREAM_ROOT_PATH_HEADER
- ALLOW_ACTOR_OVERRIDE
- APP_ROOT_PATH
- APP_DATA_DIR
- APP_UPLOADS_DIR
- APP_DB_PATH

Runtime module behavior:
- resolves repo-relative or absolute data paths
- ensures APP_DATA_DIR and APP_UPLOADS_DIR exist
- validates that APP_DB_PATH points to a file location

## Environment Configuration

Actor resolution and path behavior are controlled by these environment variables:
- USE_UPSTREAM_AUTH
  - Default: false
  - Enabled only for strict values 1 or true
  - When enabled, app can read actor identity from a trusted upstream header.

- UPSTREAM_ACTOR_HEADER
  - Default: X-Remote-User
  - Header name used for upstream actor identity when USE_UPSTREAM_AUTH is enabled.

- USE_UPSTREAM_ROOT_PATH
  - Default: false
  - Enabled only for strict values 1 or true
  - When enabled, app resolves root_path from UPSTREAM_ROOT_PATH_HEADER on each request.
  - In this mode, APP_ROOT_PATH is ignored.

- UPSTREAM_ROOT_PATH_HEADER
  - Default: X-Ingress-Path
  - Header name used for upstream root-path forwarding when USE_UPSTREAM_ROOT_PATH is enabled.

- ALLOW_ACTOR_OVERRIDE
  - Default: false
  - Enabled only for strict values 1 or true
  - When disabled, POST /actor/set and POST /actor/reset do not modify cookies.

- APP_ROOT_PATH
  - Default: empty string (mounted at site root)
  - Normalized to a leading slash with no trailing slash.
  - Used when USE_UPSTREAM_ROOT_PATH is disabled.

- APP_DATA_DIR
  - Default: data (repo-local path)
  - Can be absolute or relative; relative paths resolve from repo root.
  - Ensured to exist at startup.

- APP_UPLOADS_DIR
  - Default: data/uploads
  - Can be absolute or relative; relative paths resolve from repo root.
  - Ensured to exist at startup.

- APP_DB_PATH
  - Default: data/logbook.db
  - Can be absolute or relative; relative paths resolve from repo root.
  - Parent directory is ensured to exist at startup.

- Cookie path
  - Derived per request from the effective root_path.
  - Uses / when mounted at the site root.

## app/db/

- connection.py: sqlite connection + Row factory.
- schema.py: table/index creation in init_db() and default settings seed.
- vendors.py: vendor CRUD, archive/unarchive, delete confirmation context, permanent delete.
- entries.py: entry CRUD, logbook pagination/search helpers, vendor entry form context, related data aggregation.
- attachments.py: attachment metadata CRUD, upload writing, safe path resolution, file cleanup helpers.
- labels.py: label CRUD/search and vendor/entry label assignment helpers.
- settings.py: singleton settings read/update helpers with self-healing row insertion.

Operational preference in DB modules:
- prefer operation-level functions that perform complete actions such as create_entry_for_vendor_uid, replace_entry_labels_by_uid, delete_entry_by_uid, and delete_vendor_by_uid
- avoid generic service layers or abstraction frameworks

---

## Current Route Map

## Home

- GET / -> Home page with current settings row

## Settings

- GET /settings -> Settings form page
- POST /settings -> Save location metadata, then redirect to /

## Actor

- POST /actor/set -> Set actor_override from form actor_id when overrides are enabled; otherwise return current actor state
- POST /actor/reset -> Clear actor_override cookie when overrides are enabled

Both actor routes return JSON for fetch/JSON requests and redirects for standard form posts.

## Vendors

- GET /vendors -> Vendor list with show_archived preference from query/cookie
- GET /vendors/new -> New vendor form
- POST /vendors/new -> Create vendor and assign vendor labels
- GET /vendor/{vendor_uid} -> Vendor detail with timeline, attachments, labels, and delete_blocked banner support
- GET /vendor/{vendor_uid}/edit -> Edit vendor form
- POST /vendor/{vendor_uid}/edit -> Update vendor and replace vendor labels
- POST /vendor/{vendor_uid}/archive -> Archive vendor
- POST /vendor/{vendor_uid}/unarchive -> Unarchive vendor
- GET /vendor/{vendor_uid}/delete -> Archived-vendor delete confirmation page
- POST /vendor/{vendor_uid}/delete/confirm -> Permanently delete archived vendor and all related entries/attachments

## Logbook

- GET /logbook -> Global chronological timeline with pagination, archived-vendor toggle, and q text search

## Entries + Attachments + ICS

- GET /entries/new -> Global new-entry vendor picker
- GET /vendor/{vendor_uid}/entries/new -> New entry form for vendor
- POST /vendor/{vendor_uid}/entries -> Create entry, labels, and uploads
- GET /attachments/{attachment_uid} -> Download attachment from disk
- GET /entry/{entry_uid}/edit -> Edit existing entry, with optional next return target
- POST /entry/{entry_uid}/edit -> Update entry, labels, remove selected attachments, add uploads
- POST /entry/{entry_uid}/delete -> Delete entry and redirect to vendor detail or provided next target
- POST /calendar/export -> Generate downloadable .ics file

## Labels

- GET /labels -> Label admin page
- POST /labels/new -> Create label from JSON body
- POST /labels/{label_uid}/rename -> Rename label from JSON body
- POST /labels/{label_uid}/color -> Update label color from JSON body
- POST /labels/{label_uid}/delete -> Delete label from JSON body
- GET /api/labels/suggest?q=... -> Label autocomplete API

---

## Data Model in Practice

Core persistence model:
- vendors
- entries
- attachments
- labels
- vendor_labels
- entry_labels
- settings

Behavior model:
- Entries are the chronological source record.
- Labels are optional metadata for organization and filtering.
- Attachments are file-backed and linked to entries, with file + DB lifecycle owned in app/db/attachments.py.
- Settings is a singleton row (id = 1) used on the home page.
- Actor context is resolved per request from override cookie -> upstream header -> default user.

---

## UID-Based Flow Examples

## Example: Edit Entry

1. Route handler receives entry_uid from /entry/{entry_uid}/edit.
2. Route validates timestamps, attachment uploads, and optional internal redirect target.
3. Route calls update_entry_by_uid(entry_uid=..., ...).
4. Route calls replace_entry_labels_by_uid(entry_uid=..., label_uids=..., new_label_names=...).
5. Route calls delete_entry_attachment_by_uid_for_entry_uid(entry_uid, attachment_uid) for removals.
6. Route calls store_attachment_uploads_for_entry_uid(entry_uid, uploads, ...).
7. Route redirects to the supplied next target or back to the vendor detail page.

Primary keys remain internal to DB modules during all operations.

## Example: Delete Vendor

1. Route receives vendor_uid at /vendor/{vendor_uid}/delete/confirm.
2. Route verifies the vendor exists and is already archived.
3. Route calls delete_vendor_by_uid(vendor_uid).
4. DB layer resolves vendor_uid -> vendor id, gathers entry IDs, deletes attachment files, then removes attachment rows, entry label rows, entry rows, vendor label rows, and the vendor row.
5. Route redirects to the vendor list with show_archived=1.

---

## Operational Notes

- First app startup initializes schema through lifespan -> init_db().
- settings helpers also self-heal the singleton row when absent.
- Development schema changes are currently applied by recreating APP_DB_PATH instead of running migrations.
- Upload size cap is 10 MB per file.
- Attachment uploads must include a filename extension.
- Attachment path checks prevent file access outside APP_UPLOADS_DIR.
- Entry creation intentionally no-ops when all entry fields, labels, and attachments are blank.
- Archived vendors cannot accept new entries.
- Vendors must be archived before permanent deletion is allowed.
- Logbook ordering uses entry_interaction_at when present, otherwise entry_created_at.
- Entry interaction timestamps must be UTC and are normalized to ISO 8601 `Z` form.
- Logbook search matches entry title, body, representative name, vendor name, and entry label names.
- Vendor-list and logbook archived toggles persist through the `show_archived_vendors` cookie, scoped to the effective root path.
