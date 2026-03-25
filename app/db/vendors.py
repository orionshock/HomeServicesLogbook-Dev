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


def get_vendor_delete_context(vendor_uid: str) -> dict | None:
    """
    Return stats and identity info needed to render the vendor delete confirmation page.

    Returns None if the vendor does not exist.
    PK resolution is internal.
    """
    with get_connection() as conn:
        vendor = conn.execute(
            """
            SELECT id, vendor_uid, vendor_name, vendor_archived_at
            FROM vendors
            WHERE vendor_uid = ?
            """,
            (vendor_uid,),
        ).fetchone()
        if vendor is None:
            return None

        vendor_id = int(vendor["id"])

        entry_count_row = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE vendor_id = ?",
            (vendor_id,),
        ).fetchone()
        entry_count = int(entry_count_row[0]) if entry_count_row else 0

        attachment_count_row = conn.execute(
            """
            SELECT COUNT(*)
            FROM attachments
            WHERE entry_id IN (SELECT id FROM entries WHERE vendor_id = ?)
            """,
            (vendor_id,),
        ).fetchone()
        attachment_count = int(attachment_count_row[0]) if attachment_count_row else 0

        return {
            "vendor_uid": str(vendor["vendor_uid"]),
            "vendor_name": str(vendor["vendor_name"]),
            "vendor_archived_at": vendor["vendor_archived_at"],
            "entry_count": entry_count,
            "attachment_count": attachment_count,
        }


def delete_vendor_by_uid(vendor_uid: str) -> bool:
    """
    Permanently delete a vendor and all of its associated data.

    Deletion order:
      1. Resolve vendor PK and gather entry IDs.
      2. Delete all attachment files (file system; fails fast on hard error, missing files OK).
      3. Delete all DB rows in a single transaction:
         attachment rows, entry-label rows, entry rows, vendor-label rows, vendor row.

    Returns False if the vendor does not exist.
    Raises ValueError if an attachment path is invalid.
    Raises OSError if a file exists but cannot be deleted.

    Label rows themselves are NOT removed.
    """
    from .attachments import delete_attachment_files_for_vendor_entries

    # Step 1: Resolve PKs
    with get_connection() as conn:
        vendor = conn.execute(
            "SELECT id FROM vendors WHERE vendor_uid = ?",
            (vendor_uid,),
        ).fetchone()
        if vendor is None:
            return False

        vendor_id = int(vendor["id"])

        entry_rows = conn.execute(
            "SELECT id FROM entries WHERE vendor_id = ?",
            (vendor_id,),
        ).fetchall()
        entry_ids = [int(row["id"]) for row in entry_rows]

    # Step 2: Delete attachment files before touching the DB
    delete_attachment_files_for_vendor_entries(entry_ids)

    # Step 3: Delete all DB rows in one transaction
    with get_connection() as conn:
        if entry_ids:
            placeholders = ",".join("?" for _ in entry_ids)
            conn.execute(
                f"DELETE FROM attachments WHERE entry_id IN ({placeholders})",
                tuple(entry_ids),
            )
            conn.execute(
                f"DELETE FROM entry_labels WHERE entry_id IN ({placeholders})",
                tuple(entry_ids),
            )
            conn.execute(
                f"DELETE FROM entries WHERE id IN ({placeholders})",
                tuple(entry_ids),
            )
        conn.execute(
            "DELETE FROM vendor_labels WHERE vendor_id = ?",
            (vendor_id,),
        )
        conn.execute(
            "DELETE FROM vendors WHERE id = ?",
            (vendor_id,),
        )

    return True