"""
db/connection.py
----------------
Provides a per-request connection via FastAPI dependency injection.
"""

import MySQLdb
from contextlib import contextmanager
from app.config import settings


def get_connection() -> MySQLdb.Connection:
    """Create and return a new MySQL connection."""
    return MySQLdb.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        passwd=settings.db_password,
        db=settings.db_name,
        charset="utf8mb4",
        autocommit=False,
    )


@contextmanager
def get_cursor(conn: MySQLdb.Connection):
    """
    Context manager that yields a DictCursor and handles
    commit / rollback automatically.
    """
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# FastAPI dependency — one connection per request, closed when done
# ---------------------------------------------------------------------------
def get_db():
    """
    FastAPI dependency.
    Usage:
        @router.get("/")
        def my_endpoint(db: MySQLdb.Connection = Depends(get_db)):
            ...
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()