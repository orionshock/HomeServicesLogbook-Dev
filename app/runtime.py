"""Runtime configuration and path resolution for local app execution."""

import os
from collections.abc import Mapping
from pathlib import Path

from app.utils import normalize_root_path


def _is_enabled_env(value: str | None, *, default: bool = False) -> bool:
    """Interpret strict enable flags used by security-related env vars."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true"}


def _resolve_runtime_path(value: str | None, *, default: Path, repo_root: Path) -> Path:
    """Resolve configured paths, supporting both absolute and repo-relative values."""
    try:
        raw_value = (value or "").strip()
        if not raw_value:
            configured_path = default
        else:
            configured_path = Path(raw_value).expanduser()

        if not configured_path.is_absolute():
            configured_path = repo_root / configured_path

        return configured_path.resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise RuntimeError(f"Invalid configured path '{value}': {exc}") from exc


def cookie_path_from_root_path(root_path: str) -> str:
    """Scope cookies to the mounted app path for proxy/subpath deployments."""
    if not root_path or root_path == "/":
        return "/"
    return root_path


def resolve_effective_root_path(headers: Mapping[str, str]) -> str:
    """Resolve effective root path from request headers and configured env behavior."""
    if USE_UPSTREAM_ROOT_PATH:
        if not UPSTREAM_ROOT_PATH_HEADER:
            return ""
        header_root_path = normalize_root_path(headers.get(UPSTREAM_ROOT_PATH_HEADER))
        if header_root_path is None:
            return ""
        return header_root_path

    return APP_ROOT_PATH


def _ensure_directory(path: Path, *, env_name: str) -> None:
    """Create and validate a required directory path."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"Invalid {env_name}: could not create directory at '{path}': {exc}") from exc

    if not path.is_dir():
        raise RuntimeError(f"Invalid {env_name}: '{path}' is not a directory")


def _validate_db_path(path: Path, *, env_name: str) -> None:
    """Validate that the DB path points to a file location and parent directory exists."""
    if path.exists() and path.is_dir():
        raise RuntimeError(f"Invalid {env_name}: '{path}' points to a directory; expected a file path")

    _ensure_directory(path.parent, env_name=f"{env_name} parent directory")


USE_UPSTREAM_AUTH = _is_enabled_env(os.getenv("USE_UPSTREAM_AUTH"), default=False)
UPSTREAM_ACTOR_HEADER = (os.getenv("UPSTREAM_ACTOR_HEADER", "X-Remote-User") or "").strip()
USE_UPSTREAM_ROOT_PATH = _is_enabled_env(os.getenv("USE_UPSTREAM_ROOT_PATH"), default=False)
UPSTREAM_ROOT_PATH_HEADER = (os.getenv("UPSTREAM_ROOT_PATH_HEADER", "X-Ingress-Path") or "").strip()
ALLOW_ACTOR_OVERRIDE = _is_enabled_env(os.getenv("ALLOW_ACTOR_OVERRIDE"), default=False)
APP_ROOT_PATH = normalize_root_path(os.getenv("APP_ROOT_PATH")) or ""

REPO_ROOT = Path(__file__).resolve().parent.parent

# Default to repo-local data so local development stays self-contained.
APP_DATA_DIR = _resolve_runtime_path(
    os.getenv("APP_DATA_DIR"),
    default=Path("data"),
    repo_root=REPO_ROOT,
)
# Upload and DB locations can be overridden independently when needed.
APP_UPLOADS_DIR = _resolve_runtime_path(
    os.getenv("APP_UPLOADS_DIR"),
    default=APP_DATA_DIR / "uploads",
    repo_root=REPO_ROOT,
)
APP_DB_PATH = _resolve_runtime_path(
    os.getenv("APP_DB_PATH"),
    default=APP_DATA_DIR / "logbook.db",
    repo_root=REPO_ROOT,
)

_ensure_directory(APP_DATA_DIR, env_name="APP_DATA_DIR")
_ensure_directory(APP_UPLOADS_DIR, env_name="APP_UPLOADS_DIR")
_validate_db_path(APP_DB_PATH, env_name="APP_DB_PATH")