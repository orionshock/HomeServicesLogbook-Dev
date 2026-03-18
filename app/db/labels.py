import sqlite3

from app.utils import is_valid_hex_color, make_uid, normalize_label_name

from .connection import get_connection


def list_labels() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, label_uid, label_name AS name, label_color AS color,
                   label_created_at AS created_at, label_created_by AS created_by,
                   label_updated_at AS updated_at, label_updated_by AS updated_by
            FROM labels
            ORDER BY label_name COLLATE NOCASE
            """
        ).fetchall()


def get_label_by_uid(label_uid: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, label_uid, label_name AS name, label_color AS color,
                   label_created_at AS created_at, label_created_by AS created_by,
                   label_updated_at AS updated_at, label_updated_by AS updated_by
            FROM labels
            WHERE label_uid = ?
            """,
            (label_uid,),
        ).fetchone()


def get_label_by_name(name: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, label_uid, label_name AS name, label_color AS color,
                   label_created_at AS created_at, label_created_by AS created_by,
                   label_updated_at AS updated_at, label_updated_by AS updated_by
            FROM labels
            WHERE label_name = ? COLLATE NOCASE
            """,
            (name,),
        ).fetchone()


def create_label(
    label_uid: str,
    name: str,
    color: str | None,
    created_at: str,
    created_by: str | None,
) -> int:
    if not is_valid_hex_color(color):
        raise ValueError(f"Invalid color format: {color}. Must be hex (e.g., #RRGGBB)")

    with get_connection() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO labels (
                    label_uid, label_name, label_color,
                    label_created_at, label_created_by
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (label_uid, name, color, created_at, created_by),
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(f"A label named \"{name}\" already exists.")


def update_label_by_uid(
    label_uid: str,
    name: str,
    color: str | None,
    updated_at: str,
    updated_by: str | None,
) -> bool:
    if not is_valid_hex_color(color):
        raise ValueError(f"Invalid color format: {color}. Must be hex (e.g., #RRGGBB)")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM labels WHERE label_uid = ?",
            (label_uid,),
        ).fetchone()
        if existing is None:
            return False

        try:
            conn.execute(
                """
                UPDATE labels
                SET
                    label_name = ?,
                    label_color = ?,
                    label_updated_at = ?,
                    label_updated_by = ?
                WHERE label_uid = ?
                """,
                (name, color, updated_at, updated_by, label_uid),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("A label with that name already exists") from exc

        return True


def delete_label_by_uid(label_uid: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM labels WHERE label_uid = ?",
            (label_uid,),
        )
        return cursor.rowcount > 0


def search_labels_by_name(query: str, limit: int = 10) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, label_uid, label_name AS name, label_color AS color,
                   label_created_at AS created_at, label_created_by AS created_by,
                   label_updated_at AS updated_at, label_updated_by AS updated_by
            FROM labels
            WHERE label_name LIKE ? COLLATE NOCASE
            ORDER BY label_name COLLATE NOCASE
            LIMIT ?
            """,
            (f"%{query}%", limit),
        ).fetchall()


def list_labels_for_vendor_id(vendor_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT l.id, l.label_uid, l.label_name AS name, l.label_color AS color
            FROM vendor_labels vl
            JOIN labels l ON l.id = vl.label_id
            WHERE vl.vendor_id = ?
            ORDER BY l.label_name COLLATE NOCASE
            """,
            (vendor_id,),
        ).fetchall()


def replace_vendor_labels(vendor_id: int, label_ids: list[int]) -> None:
    unique_label_ids = list(dict.fromkeys(label_ids))
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM vendor_labels WHERE vendor_id = ?",
            (vendor_id,),
        )
        if unique_label_ids:
            conn.executemany(
                "INSERT INTO vendor_labels (vendor_id, label_id) VALUES (?, ?)",
                [(vendor_id, label_id) for label_id in unique_label_ids],
            )


def list_labels_for_entry_id(entry_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT l.id, l.label_uid, l.label_name AS name, l.label_color AS color
            FROM entry_labels el
            JOIN labels l ON l.id = el.label_id
            WHERE el.entry_id = ?
            ORDER BY l.label_name COLLATE NOCASE
            """,
            (entry_id,),
        ).fetchall()


def replace_entry_labels(entry_id: int, label_ids: list[int]) -> None:
    unique_label_ids = list(dict.fromkeys(label_ids))
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM entry_labels WHERE entry_id = ?",
            (entry_id,),
        )
        if unique_label_ids:
            conn.executemany(
                "INSERT INTO entry_labels (entry_id, label_id) VALUES (?, ?)",
                [(entry_id, label_id) for label_id in unique_label_ids],
            )


def resolve_submitted_labels(
    label_uids: list[str],
    new_label_names: list[str],
    actor: str | None,
    now: str,
) -> list[int]:
    resolved_ids: list[int] = []
    seen_ids: set[int] = set()

    for label_uid in label_uids:
        row = get_label_by_uid((label_uid or "").strip())
        if row is None:
            continue
        label_id = int(row["id"])
        if label_id in seen_ids:
            continue
        seen_ids.add(label_id)
        resolved_ids.append(label_id)

    for raw_name in new_label_names:
        normalized_name = normalize_label_name(raw_name)
        if not normalized_name:
            continue

        row = get_label_by_name(normalized_name)
        if row is None:
            try:
                new_id = create_label(
                    label_uid=make_uid("label"),
                    name=normalized_name,
                    color=None,
                    created_at=now,
                    created_by=actor,
                )
            except ValueError:
                retry_row = get_label_by_name(normalized_name)
                if retry_row is None:
                    continue
                new_id = int(retry_row["id"])
            label_id = new_id
        else:
            label_id = int(row["id"])

        if label_id in seen_ids:
            continue
        seen_ids.add(label_id)
        resolved_ids.append(label_id)

    return resolved_ids