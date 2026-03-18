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
        -> SQLite (data/logbook.db)
      -> Jinja template render (templates/*.html)
  -> HTML response
```

For uploads:
- Files are written to uploads/YYYY/MM.
- SQLite stores attachment metadata and relative file path.

---

## Current Folder Structure

```text
HomeServicesLogbook-Dev/
|-- app/
|   |-- main.py
|   |-- utils.py
|   |-- db/
|   |   |-- connection.py
|   |   |-- schema.py
|   |   |-- vendors.py
|   |   |-- entries.py
|   |   |-- attachments.py
|   |   |-- labels.py
|   |   `-- __init__.py
|   `-- routes/
|       |-- __init__.py
|       |-- home.py
|       |-- vendors.py
|       |-- entries.py
|       |-- labels.py
|       `-- __init__.py
|-- templates/
|   |-- base.html
|   |-- home.html
|   |-- vendor_listing.html
|   |-- vendor_form.html
|   |-- vendor_detail.html
|   |-- entry_form.html
|   |-- label_admin.html
|   |-- 404.html
|   |-- error.html
|   `-- partials/
|       |-- vendor_header_card.html
|       |-- log_entry_card.html
|       `-- label_picker.html
|-- static/
|   |-- css/
|   |   |-- base.css
|   |   |-- layout.css
|   |   |-- components.css
|   |   |-- forms.css
|   |   |-- home.css
|   |   |-- vendors.css
|   |   |-- entries.css
|   |   `-- labels.css
|   `-- js/
|       |-- entry_form.js
|       |-- label_picker.js
|       |-- label_admin.js
|       |-- vendor_header_card.js
|       |-- vendors.js
|       |-- time.js
|       |-- external_links.js
|       `-- dev_seed_routes.js
|-- data/
|   `-- logbook.db
|-- uploads/
|-- docs/
|-- requirements.txt
`-- README.md
```

---

## App Composition

## app/main.py

Responsibilities:
- Creates FastAPI app with lifespan from app/routes/home.py.
- Mounts static files at /static.
- Registers exception handlers:
  - HTTPException -> 404.html or error.html
  - RequestValidationError -> error.html (400)
  - Exception -> error.html (500)
- Adds middleware to attach request.state.current_actor.
- Includes routers:
  - home
  - vendors
  - entries
  - labels

## app/routes/__init__.py

Shared route utilities:
- BASE_DIR path resolution.
- MAX_UPLOAD_BYTES (10 MB).
- Template rendering helper with current actor context.
- Temporary actor resolver (hardcoded dev actor).

## app/db/

- connection.py: sqlite connection + Row factory.
- schema.py: table/index creation in init_db().
- vendors.py: vendor CRUD + archive/unarchive.
- entries.py: entry CRUD/listing.
- attachments.py: attachment metadata CRUD/listing.
- labels.py: label CRUD/search and vendor/entry label assignment helpers.

---

## Current Route Map

## Home

- GET / -> Home page

## Vendors

- GET /vendors -> Vendor list (respects show_archived preference via query/cookie)
- GET /vendors/new -> New vendor form
- POST /vendors/new -> Create vendor + assign vendor labels
- GET /vendor/{vendor_uid} -> Vendor detail with timeline, attachments, labels
- GET /vendor/{vendor_uid}/edit -> Edit vendor form
- POST /vendor/{vendor_uid}/edit -> Update vendor + replace vendor labels
- POST /vendor/{vendor_uid}/archive -> Archive vendor
- POST /vendor/{vendor_uid}/unarchive -> Unarchive vendor

## Entries + Attachments + ICS

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

Behavior model:
- Entries are the chronological source record.
- Labels are optional metadata for organization/filtering.
- Attachments are file-backed and linked to entries.

---

## Operational Notes

- First app startup initializes schema through lifespan -> init_db().
- Development schema changes are applied by recreating data/logbook.db.
- Upload size cap is 10 MB per file.
- Attachment path checks prevent file access outside uploads/.
