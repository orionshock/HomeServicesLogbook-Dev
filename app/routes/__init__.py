from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.runtime import ALLOW_ACTOR_OVERRIDE

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

templates = Jinja2Templates(directory="templates")


def _path_has_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}/")


def path_for(request: Request, endpoint_name: str, **path_params) -> str:
    path = str(request.app.url_path_for(endpoint_name, **path_params))
    root_path = (request.scope.get("root_path") or "").rstrip("/")
    if not root_path or _path_has_prefix(path, root_path):
        return path

    if path == "/":
        return root_path

    return f"{root_path}{path}"


def _resolve_template_actor(request: Request) -> dict[str, str | None]:
    from app.actor import resolve_current_actor

    return resolve_current_actor(request)

def render_template(request: Request, template_name: str, context: dict | None = None):
    def url_for(endpoint_name: str, **path_params) -> str:
        return path_for(request, endpoint_name, **path_params)

    payload = {
        "request": request,
        "url_for": url_for,
        "current_actor": getattr(request.state, "current_actor", _resolve_template_actor(request)),
        "allow_actor_override": ALLOW_ACTOR_OVERRIDE,
    }
    if context:
        payload.update(context)
    return templates.TemplateResponse(template_name, payload)
