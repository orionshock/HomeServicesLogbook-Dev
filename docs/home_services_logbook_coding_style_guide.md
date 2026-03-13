# Home Services Logbook - Coding Style Guide

## Purpose

This document defines the coding style and implementation preferences for the Home Services Logbook project.

It exists to guide:
- the human developer
- GitHub Copilot
- future contributors

The goals are:
- readability
- maintainability
- simplicity
- consistency

This project should feel like a well-organized small utility, not an overengineered framework demo.

---

## General Principles

### Prefer simple code
Favor straightforward, boring, readable code over clever abstractions.

Good:
- small functions
- obvious control flow
- descriptive names
- explicit behavior

Avoid:
- unnecessary indirection
- deep class hierarchies
- excessive abstraction
- premature optimization
- clever one-liners that reduce readability

### Prefer maintainability over novelty
If two solutions work, choose the one that will be easier to understand six months later.

### Minimize dependencies
Do not add a new dependency unless it provides clear value.

Before introducing a package, ask:
- does the standard library already handle this?
- is the dependency worth the maintenance cost?
- does it make deployment harder?

### Build incrementally
Prefer small, reviewable steps over large rewrites.

Good pattern:
- create minimal route
- make it work
- improve structure
- add polish later

Avoid giant speculative architecture.

---

## Python Style

### Python version
Write code compatible with the project Python version in use.

### Function style
Prefer small functions with clear responsibilities.

Good:
- one function reads vendor by UID
- one function inserts entry
- one function stores uploaded file metadata

Avoid large multi-purpose functions.

### Naming
Use descriptive snake_case names.

Good:
- get_vendor_by_uid
- create_entry
- generate_entry_uid
- store_uploaded_file

Avoid:
- vague names like data, thing, item, misc
- unnecessary abbreviations

### Type hints
Use type hints when they improve clarity, especially in function signatures.

Example:
```python
def get_vendor_by_uid(vendor_uid: str) -> dict | None:
    ...
```

Type hints should help readability, not become noise.

### Comments
Use comments sparingly and only where intent is not obvious.

Good comments explain:
- why something is done
- assumptions
- security constraints
- non-obvious business rules

Do not comment every obvious line.

### Error handling
Handle errors clearly and explicitly.

Prefer:
- early validation
- clear exceptions
- predictable fallback behavior

Avoid swallowing exceptions silently.

---

## FastAPI Style

### Keep routes thin
Routes should:
- receive request data
- validate it
- call service/database helpers
- return response/template

Routes should not contain large blocks of business logic.

### Prefer explicit route names
Use clear route names and paths.

Examples:
- /vendors
- /vendor/{vendor_uid}
- /vendor/{vendor_uid}/entry
- /entry/{entry_uid}/attachment

Avoid ambiguous route naming.

### Use standard FastAPI patterns
Use:
- Request objects where needed
- Form or UploadFile for forms/uploads
- TemplateResponse for HTML pages

Do not invent custom infrastructure unless there is a real need.

---

## Template Style (Jinja)

### Keep templates simple
Templates are for presentation, not business logic.

Templates may:
- loop over items
- display conditionals
- render data
- call simple filters

Templates should not:
- perform complex transformations
- contain application logic
- become hard to read

### Favor readability
Keep template structure clean and easy to scan.

Use:
- semantic HTML when practical
- clear section headings
- predictable layout blocks

### Escape by default
Do not disable escaping without a strong reason.

User-provided content should render as text unless a specific sanitization strategy exists.

---

## Database Style

### Use parameterized SQL only
Never build SQL queries with string interpolation.

Bad:
```python
sql = f"SELECT * FROM vendors WHERE vendor_uid = '{vendor_uid}'"
```

Good:
```python
sql = "SELECT * FROM vendors WHERE vendor_uid = ?"
cursor.execute(sql, (vendor_uid,))
```

### Keep SQL readable
Write clear SQL statements.

Prefer:
- multiline SQL where helpful
- explicit column names when useful
- simple query structure

Avoid cryptic or compressed SQL.

### No ORM unless explicitly chosen later
Default approach is direct SQLite access with simple helper functions.

Do not introduce SQLAlchemy or other ORMs unless explicitly requested.

### Centralize DB access
Keep database access in dedicated helper/service modules rather than scattering SQL everywhere.

Good examples:
- app/db/vendors.py
- app/db/entries.py
- app/db/attachments.py

or a similarly simple structure.

---

## File Handling Style

### Never trust uploaded filenames
Always generate a safe internal filename.

Original filenames should be treated as metadata only.

### Use pathlib
Use pathlib for filesystem paths instead of hardcoded path strings.

Good:
```python
from pathlib import Path
```

### Keep paths relative where possible
Store relative paths in SQLite, not environment-specific absolute paths.

---

## HTML / UI Style

### Keep the UI utilitarian and clear
This app is a practical logbook tool.

The interface should feel:
- simple
- calm
- readable
- efficient

Do not overdesign the UI early.

### Emphasize the main workflow
The primary UX is:
- open vendor
- write note
- attach document if needed
- save
- review timeline

UI decisions should support that flow.

### Encourage append-style logging
The UI should naturally favor creating new entries over rewriting history.

---

## Security Style

### Treat all external data as untrusted
This includes:
- form input
- URL parameters
- upload metadata
- future headers from external systems

### Validate where practical
Validate:
- UID formats
- required fields
- file sizes
- allowable actions

### Do not execute user input
Never:
- pass user input into shell commands
- build SQL directly from user strings
- trust file paths from users

---

## Git and Commit Style

### Commit small logical steps
Good commit examples:
- Add FastAPI app scaffold
- Add vendor list route
- Add vendor detail template
- Add entry creation form
- Add attachment upload handling

Avoid giant mixed commits.

### Keep the main branch understandable
Each commit should represent a meaningful incremental improvement.

---

## Project-Specific Implementation Preferences

### Preferred architecture
Use:
- FastAPI
- Jinja templates
- SQLite
- filesystem uploads

### Avoid unnecessary frontend complexity
Do not introduce React, Vue, or other frontend frameworks unless explicitly requested.

### Favor vendor-centered timelines
The main center of gravity is the vendor page and its entry timeline.

### Preserve logbook philosophy
The product is:
- a household services logbook
- a document archive
- a vendor history tool

It is not:
- a CRM monster
- a ticketing platform
- a project management system

### Delay advanced features
Do not prematurely build:
- labels
- advanced search systems
- external database support
- authentication systems
- Home Assistant integration details
- revision hashing
- cryptographic verification

These are future concerns.

---

## Copilot Guidance

When generating code for this project:
- prefer incremental changes
- preserve the current simple architecture
- avoid adding dependencies casually
- avoid overengineering
- keep code readable first
- keep route handlers thin
- keep SQL parameterized
- use the docs/ directory as reference material

Copilot should optimize for clarity and practicality, not novelty.

---

## Final Rule

When in doubt, choose the solution that:
- is easier to read
- is easier to debug
- is easier to maintain
- keeps the project small and coherent
