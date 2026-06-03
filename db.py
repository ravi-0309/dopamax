"""
Database compatibility layer for Dopamax.

- Local development: uses SQLite (file 'database.db') with zero configuration.
- Production (e.g. Render + Supabase): set the DATABASE_URL environment variable
  to your Postgres connection string and the app automatically uses Postgres.

The rest of the app keeps using SQLite-style '?' placeholders; this layer
rewrites them to '%s' for Postgres transparently.
"""

import os

DATABASE_URL = os.environ.get("DATABASE_URL")
IS_PG = bool(DATABASE_URL)

if IS_PG:
    import psycopg2 as _pg
    IntegrityError = _pg.IntegrityError
else:
    import sqlite3 as _sqlite
    IntegrityError = _sqlite.IntegrityError


class _Cursor:
    """Wraps a DB-API cursor and rewrites '?' placeholders for Postgres."""

    def __init__(self, real):
        self._c = real

    def execute(self, sql, params=()):
        if IS_PG:
            sql = sql.replace("?", "%s")
        return self._c.execute(sql, params)

    def fetchone(self):
        return self._c.fetchone()

    def fetchall(self):
        return self._c.fetchall()

    @property
    def lastrowid(self):
        return getattr(self._c, "lastrowid", None)

    def __getattr__(self, name):
        return getattr(self._c, name)


class _Conn:
    """Wraps a DB-API connection so .cursor() returns a translating cursor."""

    def __init__(self, real):
        self._conn = real

    def cursor(self):
        return _Cursor(self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def close(self):
        return self._conn.close()

    def set_autocommit(self, value):
        try:
            self._conn.autocommit = value
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


def connect():
    """Open a new connection (Postgres if DATABASE_URL is set, else SQLite)."""
    if IS_PG:
        return _Conn(_pg.connect(DATABASE_URL, sslmode="require"))
    return _Conn(_sqlite.connect("database.db"))


def insert_returning_id(cursor, sql, params):
    """
    Run an INSERT and return the new row id, working on both engines.
    Pass SQLite-style '?' placeholders; they are rewritten for Postgres.
    """
    if IS_PG:
        pg_sql = sql.replace("?", "%s").rstrip().rstrip(";")
        if "returning" not in pg_sql.lower():
            pg_sql += " RETURNING id"
        cursor._c.execute(pg_sql, params)
        return cursor.fetchone()[0]
    cursor.execute(sql, params)
    return cursor.lastrowid


def pk_clause():
    """Primary-key column definition for CREATE TABLE, per engine."""
    return "SERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"


def ts_default():
    """A text 'created_at' default that works on both engines."""
    return "TEXT DEFAULT (now()::text)" if IS_PG else "TEXT DEFAULT CURRENT_TIMESTAMP"
