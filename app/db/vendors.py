import sqlite3

from .connection import get_connection


def _translate_vendor_integrity_error(exc: sqlite3.IntegrityError) -> ValueError:
    error_text = str(exc).lower()
    if "vendor_name" in error_text:
        return ValueError("Vendor name is required")
    if "vendor_uid" in error_text:
        return ValueError("A vendor with this identifier already exists")
    return ValueError("Vendor could not be saved due to invalid data")


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


def list_entry_vendor_picker_rows(include_archived: bool = False) -> list[dict]:
    """
    Return route-ready vendor picker rows using UIDs only.

    Internal PK usage is contained in DB layer.
    """
    from .labels import list_labels_for_vendor_ids

    vendors = list_vendors(include_archived=include_archived)
    labels_by_vendor_id: dict[int, list[dict]] = {}
    vendor_ids = [int(vendor["id"]) for vendor in vendors]

    for row in list_labels_for_vendor_ids(vendor_ids):
        labels_by_vendor_id.setdefault(int(row["vendor_id"]), []).append(
            {
                "label_uid": row["label_uid"],
                "name": row["name"],
                "color": row["color"],
            }
        )

    picker_rows: list[dict] = []
    for vendor in vendors:
        vendor_id = int(vendor["id"])
        labels = labels_by_vendor_id.get(vendor_id, [])
        label_names = [label["name"] for label in labels]
        search_text = " ".join([vendor["vendor_name"], *label_names]).strip()
        picker_rows.append(
            {
                "vendor_uid": vendor["vendor_uid"],
                "vendor_name": vendor["vendor_name"],
                "labels": labels,
                "search_text": search_text,
            }
        )

    return sorted(picker_rows, key=lambda vendor: str(vendor["vendor_name"]).casefold())


def list_vendor_listing_rows(include_archived: bool = False) -> list[dict]:
    """
    Return route-ready vendor listing rows using UIDs only.

    Internal PK usage is contained in DB layer.
    """
    from .labels import list_labels_for_vendor_ids

    vendors = list_vendors(include_archived=include_archived)
    labels_by_vendor_id: dict[int, list[dict]] = {}
    vendor_ids = [int(vendor["id"]) for vendor in vendors]

    for row in list_labels_for_vendor_ids(vendor_ids):
        labels_by_vendor_id.setdefault(int(row["vendor_id"]), []).append(
            {
                "label_uid": row["label_uid"],
                "name": row["name"],
                "color": row["color"],
            }
        )

    listing_rows: list[dict] = []
    for vendor in vendors:
        vendor_id = int(vendor["id"])
        labels = labels_by_vendor_id.get(vendor_id, [])
        label_names = [label["name"] for label in labels]
        listing_rows.append(
            {
                "vendor_uid": vendor["vendor_uid"],
                "vendor_name": vendor["vendor_name"],
                "vendor_archived_at": vendor["vendor_archived_at"],
                "labels": labels,
                "label_names": label_names,
                "search_text": " ".join([vendor["vendor_name"], *label_names]).strip(),
            }
        )

    return sorted(listing_rows, key=lambda vendor: str(vendor["vendor_name"]).casefold())


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
        try:
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
        except sqlite3.IntegrityError as exc:
            raise _translate_vendor_integrity_error(exc) from exc


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
        try:
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
        except sqlite3.IntegrityError as exc:
            raise _translate_vendor_integrity_error(exc) from exc


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