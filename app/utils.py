import re
import uuid
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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

    raise ValueError(f"Unknown UID kind: {kind}")
