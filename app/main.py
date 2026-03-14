import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import get_connection, init_db


def _make_vendor_uid(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30]
    short = uuid.uuid4().hex[:4]
    return f"{slug}-{short}"


def _make_entry_uid() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short = uuid.uuid4().hex[:6]
    return f"{stamp}-{short}"


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

templates = Jinja2Templates(directory="templates")


@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/vendors/new")
def vendor_new_form(request: Request):
    return templates.TemplateResponse("vendor_new.html", {"request": request})


@app.post("/vendors/new")
def vendor_new_submit(
    request: Request,
    name: str = Form(...),
    category: str = Form(""),
    account_number: str = Form(""),
    portal_url: str = Form(""),
    vendor_notes: str = Form(""),
):
    vendor_uid = _make_vendor_uid(name)
    now = _now_utc()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO vendors (vendor_uid, name, category, account_number, portal_url, vendor_notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                vendor_uid,
                name,
                category or None,
                account_number or None,
                portal_url or None,
                vendor_notes or None,
                now,
            ),
        )
    return RedirectResponse(url=f"/vendor/{vendor_uid}", status_code=303)


@app.get("/vendors")
def vendor_list(request: Request):
    with get_connection() as conn:
        vendors = conn.execute(
            "SELECT * FROM vendors WHERE archived_at IS NULL ORDER BY name"
        ).fetchall()
    return templates.TemplateResponse(
        "vendors.html", {"request": request, "vendors": vendors}
    )


@app.get("/vendor/{vendor_uid}")
def vendor_detail(request: Request, vendor_uid: str):
    with get_connection() as conn:
        vendor = conn.execute(
            "SELECT * FROM vendors WHERE vendor_uid = ?",
            (vendor_uid,),
        ).fetchone()

    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    return templates.TemplateResponse(
        "vendor_detail.html",
        {"request": request, "vendor": vendor},
    )


@app.post("/vendor/{vendor_uid}/entries")
def create_vendor_entry(
    vendor_uid: str,
    body_text: str = Form(""),
    vendor_reference: str = Form(""),
    rep_name: str = Form(""),
):
    with get_connection() as conn:
        vendor = conn.execute(
            "SELECT id FROM vendors WHERE vendor_uid = ?",
            (vendor_uid,),
        ).fetchone()

        if vendor is None:
            raise HTTPException(status_code=404, detail="Vendor not found")

        conn.execute(
            """
            INSERT INTO entries (
                entry_uid,
                vendor_id,
                body_text,
                vendor_reference,
                rep_name,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                _make_entry_uid(),
                vendor["id"],
                body_text or None,
                vendor_reference or None,
                rep_name or None,
                _now_utc(),
            ),
        )

    return RedirectResponse(url=f"/vendor/{vendor_uid}", status_code=303)
