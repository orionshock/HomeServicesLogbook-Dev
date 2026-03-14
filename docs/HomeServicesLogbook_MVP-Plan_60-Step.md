# Home Services Logbook — Detailed 60-Step MVP Plan

This document breaks the Minimum Viable Product into very small, reviewable steps for use with GitHub Copilot and manual development.

Rules:
- Complete one step at a time.
- Run the app after each meaningful step.
- Keep commits small.
- Do not add features outside the step you are working on.
- If a step is unclear, prefer the simplest working implementation.

Core app model:

Vendor → Entries → Attachments

---

## Phase 1 — Repository and App Skeleton

### Step 1
Create the basic folder structure:

- app/
- templates/
- static/
- uploads/
- data/
- docs/

### Step 2
Create `app/main.py`.

### Step 3
Create a minimal FastAPI app instance in `app/main.py`.

### Step 4
Add a root route `/` that returns simple text like:
`Home Services Logbook running`

### Step 5
Run the app with:

`uvicorn app.main:app --reload`

Verify the root route works in the browser.

### Step 6
Create a `.gitignore` file and make sure it ignores:

- `.venv/`
- `__pycache__/`
- `uploads/`
- `data/`

### Step 7
Make the first commit for the basic app scaffold.

---

## Phase 2 — Template Support

### Step 8
Add Jinja template support to `app/main.py`.

### Step 9
Create `templates/base.html`.

### Step 10
Create a very simple layout in `base.html` with:
- page title
- top navigation placeholder
- main content block

### Step 11
Create `templates/home.html`.

### Step 12
Change the `/` route to render `home.html` instead of plain text.

### Step 13
Put a simple message on the home page describing the app.

### Step 14
Verify server-rendered templates are working.

### Step 15
Commit the template setup.

---

## Phase 3 — SQLite Setup

### Step 16
Create `app/db.py`.

### Step 17
Define a database path that points to a file inside `data/`.

### Step 18
Add a helper function to open a SQLite connection.

### Step 19
Make sure rows can be accessed in a convenient way, such as dictionary-like access.

### Step 20
Add a schema initialization function.

### Step 21
Create the `vendors` table.

### Step 22
Create the `entries` table.

### Step 23
Create the `attachments` table.

### Step 24
Create recommended indexes:
- vendor UID
- entry UID
- vendor timeline
- attachment lookup

### Step 25
Call schema initialization during app startup.

### Step 26
Run the app and verify the database file appears in `data/`.

### Step 27
Commit the working database setup.

---

## Phase 4 — Vendor List and Navigation

### Step 28
Add a top navigation bar to `base.html`.

### Step 29
Add links for:
- Home
- Vendors

### Step 30
Create a route for `/vendors`.

### Step 31
Create `templates/vendors.html`.

### Step 32
On `/vendors`, query active vendors from SQLite.

### Step 33
Render the vendor list in `vendors.html`.

### Step 34
Make each vendor name link to `/vendor/{vendor_uid}`.

### Step 35
If there are no vendors, show a friendly empty-state message.

### Step 36
Verify vendor list page loads even when database is empty.

### Step 37
Commit vendor list page.

---

## Phase 5 — Add Vendor Workflow

### Step 38
Create route `/vendors/new` for GET.

### Step 39
Create `templates/vendor_new.html`.

### Step 40
Add a vendor creation form with at least:
- vendor name
- category
- account number
- portal URL
- notes

### Step 41
Create POST handling for `/vendors/new`.

### Step 42
Generate a `vendor_uid` when creating a vendor.

### Step 43
Insert the new vendor into the database.

### Step 44
After save, redirect to the vendor detail page.

### Step 45
Verify you can create one vendor successfully.

### Step 46
Commit vendor creation workflow.

---

## Phase 6 — Vendor Detail Page

### Step 47
Create route `/vendor/{vendor_uid}`.

### Step 48
Query the vendor by `vendor_uid`.

### Step 49
Create `templates/vendor_detail.html`.

### Step 50
Display vendor reference details at the top of the page.

### Step 51
Show fields only when they have values.

### Step 52
Add a simple “vendor notes” section.

### Step 53
If vendor is missing, return a clean 404 response or error page.

### Step 54
Verify the vendor detail page works for a real vendor.

### Step 55
Commit vendor detail page.

---

## Phase 7 — Create Entries

### Step 56
On the vendor detail page, add a “New Entry” form.

### Step 57
Add fields for:
- body text
- vendor reference (optional)
- rep name (optional)

### Step 58
Add a POST route to save a new entry for a vendor.

### Step 59
Generate an `entry_uid` when creating an entry.

### Step 60
Insert the entry into the database with `created_at`.

### Step 61
After saving, redirect back to the same vendor page.

### Step 62
The entry form should return blank after save.

### Step 63
Verify that saving an entry works.

### Step 64
Commit entry creation.

---

## Phase 8 — Entry Timeline

### Step 65
Query entries for the current vendor ordered by newest first.

### Step 66
Render entries on the vendor detail page.

### Step 67
Show:
- created timestamp
- body text
- vendor reference when present
- rep name when present

### Step 68
Create a clear visual separation between entries.

### Step 69
Show a friendly empty-state message when a vendor has no entries.

### Step 70
Verify the timeline updates after adding entries.

### Step 71
Commit timeline display.

---

## Phase 9 — File Upload Basics

### Step 72
Update the entry form to support file uploads.

### Step 73
Accept uploaded files using FastAPI upload handling.

### Step 74
Create a helper to generate safe stored filenames.

### Step 75
Create upload subfolders under `uploads/YYYY/MM/`.

### Step 76
Save uploaded files to disk.

### Step 77
Insert attachment metadata into the `attachments` table.

### Step 78
Keep an original, but sanitized, filename as metadata only.

### Step 79
Verify an uploaded file is saved to disk.

### Step 80
Commit basic file upload support.

---

## Phase 10 — Attachment Display and Download

### Step 81
Query attachments for each entry.

### Step 82
Render attachment names under the corresponding entry.

### Step 83
Create a route for downloading/viewing an attachment.

### Step 84
Serve the file using the saved relative path.

### Step 85
Verify you can click and open/download an uploaded file.

### Step 86
Commit attachment display and download.

---

## Phase 11 — Vendor Edit Page

### Step 87
Create GET route `/vendor/{vendor_uid}/edit`.

### Step 88
Create `templates/vendor_edit.html`.

### Step 89
Pre-fill the edit form with current vendor values.

### Step 90
Create POST route to update vendor details.

### Step 91
Update `updated_at` when vendor is edited.

### Step 92
Redirect back to the vendor detail page after save.

### Step 93
Verify editing a vendor works.

### Step 94
Commit vendor editing.

---

## Phase 12 — Basic Archive Support

### Step 95
Add an archive action for vendors.

### Step 96
Implement archive by setting `archived_at` instead of deleting.

### Step 97
Hide archived vendors from the default `/vendors` list.

### Step 98
Add an optional “show archived” toggle or a separate archived view only if simple.

### Step 99
Verify archived vendors no longer appear in the normal list.

### Step 100
Commit archive support.

---

## Phase 13 — Entry Editing Guardrails

### Step 101
Add an overflow or secondary action for editing an entry.

### Step 102
Create GET route for editing a specific entry.

### Step 103
Create `templates/entry_edit.html` or a simple edit form.

### Step 104
Allow body text, vendor reference, and rep name to be edited.

### Step 105
Update `updated_at` and `updated_by` if used.

### Step 106
Show an “edited” indicator in the timeline when an entry has been modified.

### Step 107
Make sure edit is secondary, not the main workflow.

### Step 108
Commit entry editing.

---

## Phase 14 — Better Layout and Usability

### Step 109
Improve `vendor_detail.html` layout to match the intended structure:
- vendor details at top
- note form in main area
- history visible alongside or below

### Step 110
Style buttons for:
- Save Entry
- Attach Document
- Add Calendar Event

### Step 111
Make entry timestamps easier to read.

### Step 112
Improve spacing and typography for readability.

### Step 113
Verify the page feels usable without advanced styling.

### Step 114
Commit layout polish.

---

## Phase 15 — Calendar Export

### Step 115
Create a helper function to generate `.ics` content.

### Step 116
Support fields:
- title
- date
- optional time
- description

### Step 117
Create a route that returns an `.ics` response for download.

### Step 118
Add an “Add Calendar Event” button to the vendor entry workflow.

### Step 119
Use the current note text as a default description where helpful.

### Step 120
Append a small calendar block to the in-progress note or otherwise preserve event info in the note.

### Step 121
Verify the browser downloads a valid `.ics` file.

### Step 122
Commit calendar export.

---

## Phase 16 — Error Handling and Safety

### Step 123
Add a simple 404 page template.

### Step 124
Add a simple generic error page template.

### Step 125
Handle missing vendor cases cleanly.

### Step 126
Handle missing attachment cases cleanly.

### Step 127
Validate required form inputs where needed.

### Step 128
Add file size limits if practical.

### Step 129
Verify bad requests fail safely.

### Step 130
Commit basic error handling.

---

## Phase 17 — Cleanup and Consistency

### Step 131
Review all routes for naming consistency.

### Step 132
Review templates for repeated markup that could move into the base template.

### Step 133
Review DB helper code and remove duplication where sensible.

### Step 134
Make sure SQL queries are all parameterized.

### Step 135
Make sure all paths are handled with safe path logic.

### Step 136
Make sure timestamps are stored consistently.

### Step 137
Commit cleanup pass.

---

## Phase 18 — MVP Finalization

### Step 138
Test full workflow:
- create vendor
- create entry
- upload file
- view timeline
- edit vendor
- edit entry
- archive vendor
- generate calendar export

### Step 139
Fix obvious bugs found during manual testing.

### Step 140
Make README setup instructions accurate.

### Step 141
Make sure docs in `docs/` reflect the actual implementation.

### Step 142
Tag this point as the MVP milestone in git if desired.

### Step 143
Create a short backlog list for post-MVP ideas instead of implementing them immediately.

### Step 144
Commit MVP completion.

---

## Explicitly Out of Scope Until After MVP

Do not build these before the above steps are complete:

- labels/tags
- advanced search or indexing
- multi-user auth
- Home Assistant integration
- external database support
- OCR
- cryptographic signatures
- revision hash chains
- analytics dashboards
- mobile app
- notifications/reminders beyond simple ICS export

---

## Recommended Copilot Usage

Use prompts like:

- “Implement Step 30 from docs/MVP-Plan.md.”
- “Read docs/database-schema.md and implement Steps 41–44.”
- “Implement Step 65 and keep the solution simple.”
- “Do only Step 87, not the whole next phase.”

Always review the generated code before accepting it.

---

## Definition of MVP Done

The MVP is done when the app can reliably do all of the following:

- create vendors
- view vendor detail pages
- create chronological entries
- upload and view attachments
- edit vendors and entries
- archive vendors
- export simple calendar events

At that point, the project has a strong enough foundation for future features.
