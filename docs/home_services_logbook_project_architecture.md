# Home Services Logbook - Project Architecture

## Technology Stack

| Layer     | Choice                        |
|-----------|-------------------------------|
| Language  | Python 3.11+                  |
| Web       | FastAPI                       |
| Templates | Jinja2                        |
| Database  | SQLite                        |
| Storage   | Local filesystem              |
| Frontend  | Plain HTML + CSS + minimal JS |

No build system, no frontend framework, no ORM.

---

## Layers

```
Request
  → FastAPI route (app/main.py)
    → SQLite query (app/db.py)
    → Jinja2 template render (templates/)
      → HTML response
```

File uploads go directly to disk (`uploads/`). The database stores only metadata.

---

## Folder Structure

```
HomeServicesLogbook-Dev/
├── app/
│   ├── main.py          # All routes, helpers, error handlers
│   └── db.py            # DB connection, schema init
├── templates/
│   ├── base.html        # Shared layout (nav, CSS, favicon)
│   ├── home.html        # App intro page
│   ├── vendors.html     # Vendor list (active + archived toggle)
│   ├── vendor_form.html # Shared new/edit vendor form page
│   ├── vendor_detail.html  # Vendor page: details, entry form, timeline
│   ├── entry_form.html     # Shared new/edit entry form page
│   ├── 404.html         # Custom 404 page
│   └── error.html       # Custom error page (4xx/5xx)
├── static/
│   ├── css/app.css      # All application styles
│   ├── js/entry_form.js     # Entry form UX: calendar panel, file attach, interaction timestamp handling
│   └── favicon.png
├── uploads/             # Uploaded files (organized by date)
├── data/
│   └── logbook.db       # SQLite database (auto-created on first run)
├── docs/                # Developer documentation
├── requirements.txt
└── README.md
```

---

## Key Routes

| Method | Path                          | Purpose                          |
|--------|-------------------------------|----------------------------------|
| GET    | `/`                           | Home page                        |
| GET    | `/vendors`                    | Vendor list                      |
| GET/POST | `/vendors/new`              | Create vendor                    |
| GET    | `/vendor/{uid}`               | Vendor detail + entry form       |
| GET/POST | `/vendor/{uid}/edit`        | Edit vendor reference data       |
| POST   | `/vendor/{uid}/archive`       | Archive a vendor                 |
| POST   | `/vendor/{uid}/entries`       | Create a new entry               |
| GET/POST | `/entry/{uid}/edit`         | Edit an existing entry           |
| GET    | `/attachments/{uid}`          | Download an attachment           |
| POST   | `/calendar/export`            | Generate and download .ics file  |

---

## Philosophy

Keep the system simple, predictable, and easy to maintain.

- One file for all routes (`app/main.py`)
- Schema changes require dropping and recreating `data/logbook.db` (dev mode)
- No ORM — raw parameterized SQL only
- No frontend build step — plain CSS and minimal vanilla JS
- Files stored on disk; SQLite stores metadata only

