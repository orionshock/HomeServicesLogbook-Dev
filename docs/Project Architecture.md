# Home Services Logbook - Project Architecture

## Technology Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Web | FastAPI |
| Templates | Jinja2 |
| Database | SQLite |
| Storage | Local filesystem |
| Frontend | Server-rendered HTML + minimal vanilla JS |

No frontend framework, no build system, no ORM.

---

## Runtime Flow

```text
Browser Request
  -> FastAPI app (app/main.py)
    -> Route module (app/routes/*.py)
      -> DB helper module (app/db/*.py)
        -> SQLite (APP_DB_PATH, default data/logbook.db)
      -> Jinja template render (templates/*.html)
  -> HTML response
```

For uploads:
- Files are written to APP_UPLOADS_DIR/YYYY/MM (default: data/uploads/YYYY/MM).
- SQLite stores attachment metadata and relative file path.

---

## Current Folder Structure

```text
HomeServicesLogbook-Dev/
|-- app/
|   |-- actor.py (actor resolution logic + actor override routes)
|   |-- main.py (FastAPI app setup, middleware, exception handlers, router registration)
|   |-- runtime.py (environment-driven runtime config values and path resolution)
|   |-- utils.py (shared helpers for timestamps, IDs, and validation)
|   |-- db/
|   |   |-- connection.py (SQLite connection factory with Row mapping)
|   |   |-- schema.py (schema initialization and singleton settings seed)
|   |   |-- vendors.py (vendor CRUD, listing, archive/unarchive operations)
|   |   |-- entries.py (entry CRUD, listing, and timeline helpers)
|   |   |-- attachments.py (attachment metadata persistence and lookup)
|   |   |-- labels.py (label CRUD, search, and vendor/entry label linking)
|   |   |-- settings.py (singleton settings read/update helpers for id = 1)
|   |   `-- __init__.py (barrel exports for DB helper modules)
|   `-- routes/
|       |-- __init__.py (shared path/url helpers + template rendering)
|       |-- home.py (home route and app lifespan initialization)
|       |-- vendors.py (vendor listing, create/edit, archive/unarchive routes)
|       |-- entries.py (entry create/edit routes, upload handling, ICS export)
|       |-- logbook.py (global chronological logbook route + pagination)
|       |-- labels.py (label admin page + JSON label management API routes)
|       `-- settings.py (settings form GET/POST routes)
|-- templates/
|   |-- base.html (shared shell layout, top navigation, and script blocks)
|   |-- home.html (home dashboard, launcher tiles, and dev smoke test controls)
|   |-- vendor_listing.html (vendor index with A-Z and category views)
|   |-- vendor_form.html (vendor create/edit form)
|   |-- vendor_detail.html (vendor profile and timeline landing page)
|   |-- entry_form.html (entry create/edit workflow page)
|   |-- logbook.html (global paginated logbook timeline view)
|   |-- label_admin.html (label management page)
|   |-- settings.html (location metadata settings form)
|   |-- 404.html (not-found error view)
|   |-- error.html (generic error view for 4xx/5xx responses)
|   `-- partials/
|       |-- vendor_header_card.html (shared vendor summary/header card)
|       |-- log_entry_card.html (shared timeline entry card rendering)
|       |-- logbook_entry_card.html (shared logbook page entry card rendering)
|       |-- label_picker.html (shared label picker UI fragment)
|       `-- actor_control.html (shared actor override control used in headers)
|-- static/
|   |-- css/
|   |   |-- base.css (theme tokens and foundational typography/colors)
|   |   |-- layout.css (app-shell layout primitives)
|   |   |-- components.css (shared button and reusable component styling)
|   |   |-- forms.css (input/textarea/form-field styling and settings panel sizing)
|   |   |-- home.css (home page panel and launcher tile styles)
|   |   |-- vendors.css (vendor listing/detail specific styles)
|   |   |-- entries.css (entry workflow and timeline styles)
|   |   `-- labels.css (label management and label-chip styles)
|   `-- js/
|       |-- actor_control.js (actor/user override UI)
|       |-- entry_form.js (entry form interactions, calendar, layout resizing)
|       |-- entry_vendor_picker.js (vendor selection UX for global new-entry flow)
|       |-- label_picker.js (label autocomplete and selection)
|       |-- label_admin.js (label management inline editing)
|       |-- vendor_header_card.js (phone number link formatting)
|       |-- vendors.js (A-Z and category view switching, vendor search)
|       |-- time.js (UTC to local time formatting)
|       |-- external_links.js (marking external links with icon)
|       |-- unsaved_changes.js (form dirty state detection, navigation warnings)
|       `-- smokeTester.js (dev-only smoke test and sample data route exerciser)
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

## App Composition

## app/main.py

Responsibilities:
- Creates FastAPI app with lifespan from app/routes/home.py.
- Applies root_path from APP_ROOT_PATH.
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
- MAX_UPLOAD_BYTES (10 MB).
- path_for helper that respects app root_path.
- Template rendering helper with current actor context.

## app/actor.py

Actor and override handling:
- Current actor resolver with explicit precedence:
  - actor_override cookie
  - trusted upstream header (config-gated)
  - default user
- Actor helper routes:
  - POST /actor/set
  - POST /actor/reset

## app/runtime.py

Environment normalization helpers and runtime constants:
- TRUST_UPSTREAM_AUTH
- UPSTREAM_ACTOR_HEADER
- APP_ROOT_PATH
- APP_DATA_DIR
- APP_UPLOADS_DIR
- APP_DB_PATH
- APP_COOKIE_PATH

## Environment Configuration

Actor resolution behavior is controlled by these environment variables:

- TRUST_UPSTREAM_AUTH
  - Default: false
  - When true, app can read actor identity from a trusted upstream header.
  - When false, upstream header values are ignored.

- UPSTREAM_ACTOR_HEADER
  - Default: X-Remote-User
  - Header name used for upstream actor identity when TRUST_UPSTREAM_AUTH is enabled.

- APP_ROOT_PATH
  - Default: empty (mounted at site root)
  - Normalized to a leading slash with no trailing slash.
  - Used as FastAPI root_path and by path_for when generating links.

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

- APP_COOKIE_PATH
  - Derived from APP_ROOT_PATH.
  - Used to scope actor/show-archived cookies for subpath deployments.

## app/db/

- connection.py: sqlite connection + Row factory.
- schema.py: table/index creation in init_db().
- vendors.py: vendor CRUD + archive/unarchive.
- entries.py: entry CRUD/listing.
- attachments.py: attachment metadata CRUD/listing.
- labels.py: label CRUD/search and vendor/entry label assignment helpers.
- settings.py: singleton settings read/update helpers.

---

## Current Route Map

## Home

- GET / -> Home page

## Settings

- GET /settings -> Settings form page
- POST /settings -> Save location metadata, then redirect to /

## Actor

- POST /actor/set -> Set actor_override cookie from form actor_id
- POST /actor/reset -> Clear actor_override cookie

## Vendors

- GET /vendors -> Vendor list (respects show_archived preference via query/cookie)
- GET /vendors/new -> New vendor form
- POST /vendors/new -> Create vendor + assign vendor labels
- GET /vendor/{vendor_uid} -> Vendor detail with timeline, attachments, labels
- GET /vendor/{vendor_uid}/edit -> Edit vendor form
- POST /vendor/{vendor_uid}/edit -> Update vendor + replace vendor labels
- POST /vendor/{vendor_uid}/archive -> Archive vendor
- POST /vendor/{vendor_uid}/unarchive -> Unarchive vendor

## Logbook

- GET /logbook -> Global chronological timeline with pagination and archived-vendor toggle

## Entries + Attachments + ICS

- GET /entries/new -> Global new-entry vendor picker
- GET /vendor/{vendor_uid}/entries/new -> New entry form for vendor
- POST /vendor/{vendor_uid}/entries -> Create entry, labels, and uploads
- GET /entry/{entry_uid}/edit -> Edit existing entry
- POST /entry/{entry_uid}/edit -> Update entry, labels, attachments
- GET /attachments/{attachment_uid} -> Download attachment from disk
- POST /calendar/export -> Generate downloadable .ics file

## Labels

- GET /labels -> Label admin page
- POST /labels/new -> Create label (JSON)
- POST /labels/{label_uid}/rename -> Rename label (JSON)
- POST /labels/{label_uid}/color -> Update label color (JSON)
- POST /labels/{label_uid}/delete -> Delete label (JSON)
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
- Labels are optional metadata for organization/filtering.
- Attachments are file-backed and linked to entries.
- Settings is a singleton row (id = 1) used for home page location metadata.
- Actor context is resolved per request (override cookie -> optional trusted upstream header -> default user).

---

## Operational Notes

- First app startup initializes schema through lifespan -> init_db().
- Settings singleton row (id = 1) is inserted during init when missing.
- settings access helpers also self-heal the singleton row when absent.
- Development schema changes are applied by recreating APP_DB_PATH (default data/logbook.db).
- Upload size cap is 10 MB per file.
- Attachment path checks prevent file access outside APP_UPLOADS_DIR.
- Entry creation intentionally no-ops (redirects without insert) when all entry fields, labels, and attachments are blank.
