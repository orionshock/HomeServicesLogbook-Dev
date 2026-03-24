import os
from pathlib import Path


def _is_truthy_env(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_enabled_env(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true"}


def _normalize_root_path(value: str | None) -> str:
    raw_value = (value or "").strip()
    if not raw_value or raw_value == "/":
        return ""

    if not raw_value.startswith("/"):
        raw_value = f"/{raw_value}"

    return raw_value.rstrip("/")


def _resolve_runtime_path(value: str | None, *, default: Path, repo_root: Path) -> Path:
    raw_value = (value or "").strip()
    if not raw_value:
        return default.resolve()

    configured_path = Path(raw_value).expanduser()
    if not configured_path.is_absolute():
        configured_path = repo_root / configured_path
    return configured_path.resolve()


def _cookie_path_from_root_path(root_path: str) -> str:
    # Cookies must be scoped to the mounted app path for subpath/proxy deployments.
    if not root_path or root_path == "/":
        return "/"
    return root_path


def _ensure_directory(path: Path, *, env_name: str) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"Invalid {env_name}: could not create directory at '{path}': {exc}") from exc

    if not path.is_dir():
        raise RuntimeError(f"Invalid {env_name}: '{path}' is not a directory")


def _validate_db_path(path: Path, *, env_name: str) -> None:
    if path.exists() and path.is_dir():
        raise RuntimeError(f"Invalid {env_name}: '{path}' points to a directory; expected a file path")

    _ensure_directory(path.parent, env_name=f"{env_name} parent directory")


TRUST_UPSTREAM_AUTH = _is_truthy_env(os.getenv("TRUST_UPSTREAM_AUTH"), default=False)
UPSTREAM_ACTOR_HEADER = (os.getenv("UPSTREAM_ACTOR_HEADER", "X-Remote-User") or "").strip()
ALLOW_ACTOR_OVERRIDE = _is_enabled_env(os.getenv("ALLOW_ACTOR_OVERRIDE"), default=False)
APP_ROOT_PATH = _normalize_root_path(os.getenv("APP_ROOT_PATH"))

REPO_ROOT = Path(__file__).resolve().parent.parent

# Default to repo-local data so local development stays self-contained.
APP_DATA_DIR = _resolve_runtime_path(
    os.getenv("APP_DATA_DIR"),
    default=REPO_ROOT / "data",
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

APP_COOKIE_PATH = _cookie_path_from_root_path(APP_ROOT_PATH)

_ensure_directory(APP_DATA_DIR, env_name="APP_DATA_DIR")
_ensure_directory(APP_UPLOADS_DIR, env_name="APP_UPLOADS_DIR")
_validate_db_path(APP_DB_PATH, env_name="APP_DB_PATH")