from urllib.parse import urlparse

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.routes import path_for
from app.runtime import (
    ALLOW_ACTOR_OVERRIDE,
    UPSTREAM_ACTOR_HEADER,
    USE_UPSTREAM_AUTH,
    cookie_path_from_root_path,
)
from app.utils import normalize_optional_text

ACTOR_OVERRIDE_COOKIE = "actor_override"

router = APIRouter()


def _read_upstream_actor(request: Request) -> str | None:
    if not USE_UPSTREAM_AUTH:
        return None

    if not UPSTREAM_ACTOR_HEADER:
        return None

    return normalize_optional_text(request.headers.get(UPSTREAM_ACTOR_HEADER))


def _cookie_path_for_request(request: Request) -> str:
    return cookie_path_from_root_path((request.scope.get("root_path") or "").strip())


def resolve_current_actor(request: Request) -> dict[str, str | None]:
    override_actor = None
    if ALLOW_ACTOR_OVERRIDE:
        override_actor = normalize_optional_text(request.cookies.get(ACTOR_OVERRIDE_COOKIE))
    return resolve_actor_with_override(request, override_actor)


def resolve_actor_with_override(request: Request, override_actor: str | None) -> dict[str, str | None]:
    upstream_actor = _read_upstream_actor(request)

    if override_actor:
        actor_id = override_actor
        source = "override"
    elif upstream_actor:
        actor_id = upstream_actor
        source = "upstream"
    else:
        actor_id = "user"
        source = "default"

    return {
        "actor_id": actor_id,
        "display_name": actor_id,
        "source": source,
        "upstream_actor": upstream_actor,
    }


def _is_async_request(request: Request) -> bool:
    requested_with = (request.headers.get("x-requested-with") or "").strip().lower()
    accept = (request.headers.get("accept") or "").lower()
    return requested_with == "fetch" or "application/json" in accept


def _actor_json_payload(actor: dict[str, str | None]) -> dict[str, object]:
    return {
        "ok": True,
        "current_actor": {
            "actor_id": actor["actor_id"],
            "display_name": actor["display_name"],
            "source": actor["source"],
        },
    }


def _redirect_target(request: Request) -> str:
    referer = request.headers.get("referer")
    if referer:
        parsed = urlparse(referer)
        if not parsed.netloc or parsed.netloc == request.url.netloc:
            path = parsed.path or path_for(request, "read_root")
            if parsed.query:
                path = f"{path}?{parsed.query}"
            return path
    return path_for(request, "read_root")


@router.post("/actor/set")
async def set_actor_override(request: Request, actor_id: str = Form("")):
    if not ALLOW_ACTOR_OVERRIDE:
        if _is_async_request(request):
            return JSONResponse(_actor_json_payload(resolve_current_actor(request)))
        return RedirectResponse(url=_redirect_target(request), status_code=303)

    normalized_actor = normalize_optional_text(actor_id)

    if _is_async_request(request):
        if normalized_actor:
            actor = resolve_actor_with_override(request, normalized_actor)
        else:
            actor = resolve_current_actor(request)

        response = JSONResponse(_actor_json_payload(actor))

        if normalized_actor:
            response.set_cookie(
                ACTOR_OVERRIDE_COOKIE,
                normalized_actor,
                path=_cookie_path_for_request(request),
                httponly=True,
                samesite="lax",
            )

        return response

    response = RedirectResponse(url=_redirect_target(request), status_code=303)

    if normalized_actor:
        response.set_cookie(
            ACTOR_OVERRIDE_COOKIE,
            normalized_actor,
            path=_cookie_path_for_request(request),
            httponly=True,
            samesite="lax",
        )

    return response


@router.post("/actor/reset")
async def reset_actor_override(request: Request):
    if not ALLOW_ACTOR_OVERRIDE:
        if _is_async_request(request):
            return JSONResponse(_actor_json_payload(resolve_current_actor(request)))
        return RedirectResponse(url=_redirect_target(request), status_code=303)

    if _is_async_request(request):
        actor = resolve_actor_with_override(request, None)
        response = JSONResponse(_actor_json_payload(actor))
        response.delete_cookie(ACTOR_OVERRIDE_COOKIE, path=_cookie_path_for_request(request))
        return response

    response = RedirectResponse(url=_redirect_target(request), status_code=303)
    response.delete_cookie(ACTOR_OVERRIDE_COOKIE, path=_cookie_path_for_request(request))
    return response