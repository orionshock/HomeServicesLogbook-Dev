import os


def _is_truthy_env(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_root_path(value: str | None) -> str:
    raw_value = (value or "").strip()
    if not raw_value or raw_value == "/":
        return ""

    if not raw_value.startswith("/"):
        raw_value = f"/{raw_value}"

    return raw_value.rstrip("/")


TRUST_UPSTREAM_AUTH = _is_truthy_env(os.getenv("TRUST_UPSTREAM_AUTH"), default=False)
UPSTREAM_ACTOR_HEADER = (os.getenv("UPSTREAM_ACTOR_HEADER", "X-Remote-User") or "").strip()
APP_ROOT_PATH = _normalize_root_path(os.getenv("APP_ROOT_PATH"))