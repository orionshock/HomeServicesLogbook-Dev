import sqlite3

from .connection import get_connection


def get_vendor_by_uid(vendor_uid: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM vendors WHERE vendor_uid = ?",
            (vendor_uid,),
        ).fetchone()


def list_vendors(include_archived: bool = False) -> list[sqlite3.Row]:
    with get_connection() as conn:
        if include_archived:
            return conn.execute(
                "SELECT * FROM vendors ORDER BY vendor_archived_at IS NOT NULL, vendor_name"
            ).fetchall()
        return conn.execute(
            "SELECT * FROM vendors WHERE vendor_archived_at IS NULL ORDER BY vendor_name"
        ).fetchall()


def create_vendor(
    vendor_uid: str,
    vendor_name: str,
    vendor_account_number: str | None,
    vendor_portal_url: str | None,
    vendor_portal_username: str | None,
    vendor_phone_number: str | None,
    vendor_address: str | None,
    vendor_notes: str | None,
    vendor_created_at: str,
    vendor_created_by: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO vendors (
                vendor_uid, vendor_name, vendor_account_number,
                vendor_portal_url, vendor_portal_username,
                vendor_phone_number, vendor_address,
                vendor_notes, vendor_created_at, vendor_created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                vendor_uid,
                vendor_name,
                vendor_account_number,
                vendor_portal_url,
                vendor_portal_username,
                vendor_phone_number,
                vendor_address,
                vendor_notes,
                vendor_created_at,
                vendor_created_by,
            ),
        )


def update_vendor_by_uid(
    vendor_uid: str,
    vendor_name: str,
    vendor_account_number: str | None,
    vendor_portal_url: str | None,
    vendor_portal_username: str | None,
    vendor_phone_number: str | None,
    vendor_address: str | None,
    vendor_notes: str | None,
    vendor_updated_at: str,
    vendor_updated_by: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE vendors
            SET
                vendor_name = ?,
                vendor_account_number = ?,
                vendor_portal_url = ?,
                vendor_portal_username = ?,
                vendor_phone_number = ?,
                vendor_address = ?,
                vendor_notes = ?,
                vendor_updated_at = ?,
                vendor_updated_by = ?
            WHERE vendor_uid = ?
            """,
            (
                vendor_name,
                vendor_account_number,
                vendor_portal_url,
                vendor_portal_username,
                vendor_phone_number,
                vendor_address,
                vendor_notes,
                vendor_updated_at,
                vendor_updated_by,
                vendor_uid,
            ),
        )


def archive_vendor_by_uid(vendor_uid: str, vendor_archived_at: str, vendor_updated_by: str) -> bool:
    """Returns False if the vendor does not exist."""
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT id FROM vendors WHERE vendor_uid = ?",
            (vendor_uid,),
        ).fetchone()
        if exists is None:
            return False
        conn.execute(
            """
            UPDATE vendors
            SET vendor_archived_at = ?, vendor_updated_at = ?, vendor_updated_by = ?
            WHERE vendor_uid = ?
            """,
            (vendor_archived_at, vendor_archived_at, vendor_updated_by, vendor_uid),
        )
        return True


def unarchive_vendor_by_uid(vendor_uid: str, vendor_updated_at: str, vendor_updated_by: str) -> bool:
    """Returns False if the vendor does not exist."""
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT id FROM vendors WHERE vendor_uid = ?",
            (vendor_uid,),
        ).fetchone()
        if exists is None:
            return False
        conn.execute(
            """
            UPDATE vendors
            SET vendor_archived_at = NULL, vendor_updated_at = ?, vendor_updated_by = ?
            WHERE vendor_uid = ?
            """,
            (vendor_updated_at, vendor_updated_by, vendor_uid),
        )
        return True