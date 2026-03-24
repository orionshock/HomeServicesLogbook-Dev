import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import uuid

from fastapi import UploadFile

from app.runtime import APP_UPLOADS_DIR
from app.utils import make_uid, utc_now_iso

from .connection import get_connection


def get_attachment_by_uid(attachment_uid: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT attachment_uid, entry_id, attachment_original_filename,
                   attachment_relative_path, attachment_mime_type
            FROM attachments
            WHERE attachment_uid = ?
            """,
            (attachment_uid,),
        ).fetchone()


def list_attachments_for_entry_id(entry_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, attachment_uid, entry_id, attachment_original_filename,
                   attachment_relative_path, attachment_mime_type,
                   attachment_file_size, attachment_created_at
            FROM attachments
            WHERE entry_id = ?
            ORDER BY id ASC
            """,
            (entry_id,),
        ).fetchall()


# NOTE:
# This dynamically generates "?, ?, ?" placeholders for a parameterized IN clause.
# Only placeholder tokens are interpolated, never user input.
# The actual values are still bound safely through sqlite parameters.
def list_attachments_for_entry_ids(entry_ids: list[int]) -> list[sqlite3.Row]:
    if not entry_ids:
        return []
    with get_connection() as conn:
        param_placeholders = ",".join("?" for _ in entry_ids)
        return conn.execute(
            f"""
            SELECT attachment_uid, entry_id, attachment_original_filename
            FROM attachments
            WHERE entry_id IN ({param_placeholders})
            ORDER BY id ASC
            """,
            tuple(entry_ids),
        ).fetchall()


def create_attachment(
    attachment_uid: str,
    entry_id: int,
    attachment_original_filename: str,
    attachment_stored_filename: str,
    attachment_relative_path: str,
    attachment_mime_type: str | None,
    attachment_file_size: int,
    attachment_created_by: str,
    attachment_created_at: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO attachments (
                attachment_uid, entry_id, attachment_original_filename,
                attachment_stored_filename, attachment_relative_path,
                attachment_mime_type, attachment_file_size,
                attachment_created_by, attachment_created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attachment_uid,
                entry_id,
                attachment_original_filename,
                attachment_stored_filename,
                attachment_relative_path,
                attachment_mime_type,
                attachment_file_size,
                attachment_created_by,
                attachment_created_at,
            ),
        )


def delete_attachment_by_uid_for_entry(entry_id: int, attachment_uid: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        attachment = conn.execute(
            """
            SELECT id, attachment_uid, entry_id, attachment_original_filename,
                   attachment_relative_path, attachment_mime_type
            FROM attachments
            WHERE entry_id = ? AND attachment_uid = ?
            """,
            (entry_id, attachment_uid),
        ).fetchone()
        if attachment is None:
            return None

        conn.execute(
            "DELETE FROM attachments WHERE id = ?",
            (attachment["id"],),
        )
        return attachment


def _resolve_attachment_path(relative_path: str) -> Path | None:
    """Returns the absolute path if it safely falls within APP_UPLOADS_DIR, else None."""
    rel = Path(relative_path)
    candidate = (APP_UPLOADS_DIR / rel).resolve()
    if candidate == APP_UPLOADS_DIR or APP_UPLOADS_DIR in candidate.parents:
        return candidate
    return None


def delete_attachment_files_for_entry(entry_id: int) -> None:
    """
    Validates and deletes attachment files for all attachments belonging to entry_id.

    - Missing files are silently skipped.
    - Path-traversal or directory targets raise ValueError.
    - Files that exist but cannot be deleted raise OSError.

    Does NOT modify any DB rows.
    """
    attachments = list_attachments_for_entry_id(entry_id)
    for attachment in attachments:
        relative_path = str(attachment["attachment_relative_path"] or "").strip()
        filename = str(attachment["attachment_original_filename"] or "").strip() or "(unknown filename)"
        relative_display = relative_path or "(empty path)"

        abs_path = _resolve_attachment_path(relative_path)
        if abs_path is None:
            raise ValueError(
                f"Attachment path escapes uploads root for '{filename}' "
                f"(path: {relative_display})"
            )

        if abs_path.exists() and abs_path.is_dir():
            raise ValueError(
                f"Attachment path is a directory for '{filename}' "
                f"(path: {relative_display})"
            )

        if not abs_path.exists():
            continue

        try:
            abs_path.unlink()
        except OSError as exc:
            raise OSError(
                f"Could not delete attachment '{filename}' "
                f"(path: {relative_display}): {exc.strerror or 'unknown error'}"
            ) from exc


def resolve_attachment_disk_path(relative_path: str) -> Path | None:
    """Public path resolver for use in route layer (e.g. serving attachment downloads)."""
    return _resolve_attachment_path(relative_path)


def delete_attachment_file(relative_path: str) -> None:
    """Delete a single attachment file by relative path. A missing file is silently ignored."""
    abs_path = _resolve_attachment_path(relative_path)
    if abs_path is None:
        return
    if abs_path.exists() and abs_path.is_file():
        abs_path.unlink()


def _make_stored_filename(original_name: str) -> str:
    ext = Path(original_name or "").suffix.lower()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short = uuid.uuid4().hex[:6]
    return f"{stamp}-{short}{ext}"


def _sanitize_original_filename(filename: str) -> str:
    basename = Path(filename or "").name
    sanitized = re.sub(r"\s+", "_", basename)
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", sanitized)
    sanitized = re.sub(r"_+", "_", sanitized)
    sanitized = sanitized.strip("._")
    return (sanitized or "uploaded-file")[:255]


def store_attachment_upload(
    upload: UploadFile,
    entry_id: int,
    actor: str,
    max_upload_bytes: int,
) -> None:
    """Write an uploaded file to disk and insert the attachment record into the DB."""
    now = datetime.now(timezone.utc)
    relative_dir = Path(now.strftime("%Y")) / now.strftime("%m")
    absolute_dir = APP_UPLOADS_DIR / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    attachment_original_filename = _sanitize_original_filename(upload.filename or "")
    if not Path(attachment_original_filename).suffix:
        raise ValueError("Attachment filename must include an extension")

    attachment_stored_filename = _make_stored_filename(attachment_original_filename)
    # Store path relative to APP_UPLOADS_DIR.
    attachment_relative_path = relative_dir / attachment_stored_filename
    disk_path = absolute_dir / attachment_stored_filename

    bytes_written = 0
    chunk_size = 1024 * 1024
    try:
        with disk_path.open("wb") as out:
            while True:
                chunk = upload.file.read(chunk_size)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_upload_bytes:
                    raise ValueError(
                        f"Attachment exceeds {max_upload_bytes // (1024 * 1024)} MB size limit"
                    )
                out.write(chunk)
    except ValueError:
        if disk_path.exists():
            disk_path.unlink()
        raise
    except Exception:
        if disk_path.exists():
            disk_path.unlink()
        raise
    finally:
        upload.file.close()

    create_attachment(
        attachment_uid=make_uid("attachment"),
        entry_id=entry_id,
        attachment_original_filename=attachment_original_filename,
        attachment_stored_filename=attachment_stored_filename,
        attachment_relative_path=str(attachment_relative_path).replace("\\", "/"),
        attachment_mime_type=upload.content_type,
        attachment_file_size=bytes_written,
        attachment_created_by=actor,
        attachment_created_at=utc_now_iso(),
    )


def store_attachment_uploads(
    uploads: list[UploadFile],
    entry_id: int,
    actor: str,
    max_upload_bytes: int,
) -> None:
    """Write multiple uploaded files to disk and insert their attachment records."""
    for upload in uploads:
        store_attachment_upload(upload, entry_id=entry_id, actor=actor, max_upload_bytes=max_upload_bytes)