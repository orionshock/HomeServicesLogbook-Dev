import sqlite3

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