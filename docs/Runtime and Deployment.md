# Home Services Logbook - Runtime and Deployment

This document holds the operational setup details for running the app locally or in a container.

## Local Development

### Linux / POSIX Shell

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the local dev server:

```bash
source .venv/bin/activate
export ALLOW_ACTOR_OVERRIDE=true
export APP_DATA_DIR=./data
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If you want to test reverse-proxy behavior such as forwarded actor identity and dynamic root paths, start Uvicorn with these environment settings instead:

```bash
source .venv/bin/activate
export ALLOW_ACTOR_OVERRIDE=false
export APP_DATA_DIR=./data
export USE_UPSTREAM_AUTH=true
export UPSTREAM_ACTOR_HEADER=X-Remote-User
export USE_UPSTREAM_ROOT_PATH=true
export UPSTREAM_ROOT_PATH_HEADER=X-Ingress-Path
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On startup, the app creates the data directories if needed and initializes the SQLite schema.

## Docker

The repository includes a `Dockerfile` and `docker-compose.yml`.

Build and run with Compose:

```bash
docker compose up --build
```

Container defaults:

- `APP_DATA_DIR=/data`
- `APP_UPLOADS_DIR=/data/uploads`
- `APP_DB_PATH=/data/logbook.db`
- port `8000`

Compose mounts a named volume at `/data` so the database and uploads persist across container restarts.

## Runtime Configuration

The current runtime is driven by environment variables in `app/runtime.py`:

- `APP_DATA_DIR`: base runtime data directory
- `APP_UPLOADS_DIR`: upload storage root
- `APP_DB_PATH`: SQLite file path
- `APP_ROOT_PATH`: static mounted subpath when not using forwarded root-path headers
- `USE_UPSTREAM_ROOT_PATH`: trust a forwarded root path per request
- `UPSTREAM_ROOT_PATH_HEADER`: header used when dynamic root path is enabled
- `USE_UPSTREAM_AUTH`: trust an upstream actor header
- `UPSTREAM_ACTOR_HEADER`: header used for upstream actor identity
- `ALLOW_ACTOR_OVERRIDE`: permit local actor override cookies

Relative paths resolve from the repository root. The app normalizes root paths and scopes cookies to the effective mounted path.

## Operational Notes

- Schema setup is done at startup by `init_db()`.
- Attachment downloads are served from safe paths resolved under the configured uploads root.