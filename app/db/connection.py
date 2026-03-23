import sqlite3
from app.runtime import APP_DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(APP_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn