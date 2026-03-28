"""Shared text, UID, and timestamp utility helpers."""

import re
import uuid
from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Return current UTC time in ISO 8601 format with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_optional_text(value: str | None) -> str | None:
    """Trim text and return None when the result is empty."""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def normalize_root_path(value: str | None) -> str | None:
    """Normalize a root path value or return None when invalid."""
    normalized = normalize_optional_text(value)
    if normalized is None or normalized == "/":
        return ""

    lowered = normalized.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return None

    if "\\" in normalized or "?" in normalized or "#" in normalized:
        return None

    if " " in normalized or "\t" in normalized or "\r" in normalized or "\n" in normalized:
        return None

    normalized = f"/{normalized.lstrip('/')}"
    normalized = normalized.rstrip("/")
    return normalized or ""


def normalize_label_name(value: str | None) -> str | None:
    """Normalize label text and collapse internal whitespace."""
    normalized = normalize_optional_text(value)
    if normalized is None:
        return None
    return re.sub(r"\s+", " ", normalized)


def is_valid_hex_color(value: str | None) -> bool:
    """
    Validate optional hex color input.
    Accepts #RRGGBB or #RRGGBBAA; empty values are allowed.
    """
    if not value:
        return True

    normalized = (value or "").strip()
    if not normalized:
        return True

    return bool(re.match(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$", normalized))


def make_uid(kind: str, name: str | None = None) -> str:
    """Generate a stable-format UID for each supported record type."""
    if kind == "vendor":
        slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:30]
        short = uuid.uuid4().hex[:4]
        return f"{slug}-{short}"

    if kind == "entry":
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        short = uuid.uuid4().hex[:6]
        return f"{stamp}-{short}"

    if kind == "attachment":
        return uuid.uuid4().hex

    if kind == "label":
        return uuid.uuid4().hex

    raise ValueError(f"Unknown UID kind: {kind}")


def normalize_required_text(value: str, field_name: str) -> str:
    """Normalize required form text and raise when blank."""
    normalized = re.sub(r"\s+", " ", (value or "").strip())
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized
