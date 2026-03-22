from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.db import (
    create_label,
    delete_label_by_uid,
    get_label_by_uid,
    list_labels,
    search_labels_by_name,
    update_label_by_uid,
)
from app.routes import path_for, render_template
from app.utils import is_valid_hex_color, make_uid, normalize_label_name, utc_now_iso

router = APIRouter()


def normalize_optional_color(value: str) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None

    if not is_valid_hex_color(normalized):
        raise HTTPException(
            status_code=400,
            detail="Color must be a valid hex code (e.g., #2f6f9b or #2f6f9baa)",
        )

    return normalized


@router.get("/labels")
def labels_list(request: Request):
    return render_template(
        request,
        "label_admin.html",
        {
            "breadcrumbs": [
                {"label": "Home", "url": path_for(request, "read_root")},
                {"label": "Label Management", "url": None},
            ],
            "labels": list_labels(),
        },
    )


@router.post("/labels/new")
async def label_create_inline(request: Request):
    payload = await request.json()
    submitted_name = str(payload.get("name", "")) if isinstance(payload, dict) else ""
    submitted_color = str(payload.get("color", "")) if isinstance(payload, dict) else ""

    normalized_name = normalize_label_name(submitted_name)
    if not normalized_name:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "Label name is required"},
        )

    try:
        normalized_color = normalize_optional_color(submitted_color)
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"ok": False, "error": str(exc.detail)},
        )

    actor = request.state.current_actor["actor_id"]
    now = utc_now_iso()
    label_uid = make_uid("label", name=normalized_name)

    try:
        create_label(
            label_uid=label_uid,
            name=normalized_name,
            color=normalized_color,
            created_at=now,
            created_by=actor,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=409,
            content={"ok": False, "error": str(exc)},
        )

    created = get_label_by_uid(label_uid)
    if created is None:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "Label was not created"},
        )

    return {
        "ok": True,
        "label_uid": created["label_uid"],
        "name": created["name"],
        "color": created["color"] or "#000000",
    }


@router.post("/labels/{label_uid}/rename")
async def label_rename_inline(request: Request, label_uid: str):
    payload = await request.json()
    submitted_name = str(payload.get("name", "")) if isinstance(payload, dict) else ""

    normalized_name = normalize_label_name(submitted_name)
    if not normalized_name:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "Label name is required"},
        )

    actor = request.state.current_actor["actor_id"]
    existing = get_label_by_uid(label_uid)
    if existing is None:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "Label not found"},
        )

    try:
        found = update_label_by_uid(
            label_uid=label_uid,
            name=normalized_name,
            color=existing["color"],
            updated_at=utc_now_iso(),
            updated_by=actor,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": str(exc)},
        )

    if not found:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "Label not found"},
        )

    updated = get_label_by_uid(label_uid)
    if updated is None:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "Label not found"},
        )

    return {
        "ok": True,
        "label_uid": label_uid,
        "name": updated["name"],
        "color": updated["color"] or "#000000",
    }


@router.post("/labels/{label_uid}/color")
async def label_color_inline(request: Request, label_uid: str):
    payload = await request.json()
    submitted_color = str(payload.get("color", "")) if isinstance(payload, dict) else ""

    actor = request.state.current_actor["actor_id"]
    existing = get_label_by_uid(label_uid)
    if existing is None:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "Label not found"},
        )

    try:
        found = update_label_by_uid(
            label_uid=label_uid,
            name=existing["name"],
            color=normalize_optional_color(submitted_color),
            updated_at=utc_now_iso(),
            updated_by=actor,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": str(exc)},
        )
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"ok": False, "error": str(exc.detail)},
        )

    if not found:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "Label not found"},
        )

    updated = get_label_by_uid(label_uid)
    if updated is None:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "Label not found"},
        )

    return {
        "ok": True,
        "label_uid": label_uid,
        "color": updated["color"] or "#000000",
    }


@router.post("/labels/{label_uid}/delete")
async def label_delete_inline(label_uid: str):
    found = delete_label_by_uid(label_uid)
    if not found:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "Label not found"},
        )

    return {"ok": True, "label_uid": label_uid}


@router.get("/api/labels/suggest")
def labels_suggest(q: str = ""):
    query = (q or "").strip()
    if not query:
        return []

    return [
        {
            "label_uid": item["label_uid"],
            "name": item["name"],
            "color": item["color"],
        }
        for item in search_labels_by_name(query, limit=8)
    ]
