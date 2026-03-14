from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

templates = Jinja2Templates(directory="templates")


@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/vendors")
def vendor_list(request: Request):
    from app.db import get_connection
    with get_connection() as conn:
        vendors = conn.execute(
            "SELECT * FROM vendors WHERE archived_at IS NULL ORDER BY name"
        ).fetchall()
    return templates.TemplateResponse(
        "vendors.html", {"request": request, "vendors": vendors}
    )
