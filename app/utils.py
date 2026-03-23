import re
import uuid
from datetime import datetime, timezone

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def normalize_label_name(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    if normalized is None:
        return None
    return re.sub(r"\s+", " ", normalized)


def is_valid_hex_color(value: str | None) -> bool:
    """
    Check if value is a valid hex color code.
    Accepts: #RRGGBB or #RRGGBBAA (6 or 8 hex digits after #).
    Empty/None values return True (colors are optional).
    """
    if not value:
        return True
    
    normalized = (value or "").strip()
    if not normalized:
        return True
    
    # Must be exactly #RRGGBB (6 hex) or #RRGGBBAA (8 hex)
    return bool(re.match(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$", normalized))


def make_uid(kind: str, name: str | None = None) -> str:
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
    normalized = re.sub(r"\s+", " ", (value or "").strip())
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized
