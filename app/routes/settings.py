from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.db import get_settings, update_settings
from app.routes import path_for, render_template

router = APIRouter()


@router.get("/settings")
def settings_form(request: Request):
    return render_template(
        request,
        "settings.html",
        {
            "breadcrumbs": [
                {"label": "Home", "url": path_for(request, "read_root")},
                {"label": "Settings", "url": None},
            ],
            "settings": get_settings(),
        },
    )


@router.post("/settings")
def settings_submit(
    request: Request,
    location_name: str = Form(""),
    location_address: str = Form(""),
    location_description: str = Form(""),
):
    actor = request.state.current_actor["actor_id"]
    update_settings(
        location_name=location_name.strip(),
        location_address=location_address.strip(),
        location_description=location_description.strip(),
        updated_by=actor,
    )
    return RedirectResponse(url=path_for(request, "read_root"), status_code=303)
