"""Centralised database connection handling.

Every module goes through :func:`get_connection` / :func:`run_query` so that
swapping SQLite for MySQL/PostgreSQL later touches only this file.
"""
from __future__ import annotations

import logging
import math
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

import pandas as pd

import config

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Raised for any database failure, wrapping the driver exception."""


class _StdDev:
    """SQLite aggregate: population standard deviation (STDEV(x))."""

    def __init__(self) -> None:
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0

    def step(self, value: float | None) -> None:
        if value is None:
            return
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)

    def finalize(self) -> float | None:
        return math.sqrt(self.m2 / self.n) if self.n else None


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys on and Row access."""
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(path, check_same_thread=False)
    except sqlite3.Error as exc:  # pragma: no cover - disk / permission errors
        raise DatabaseError(f"Cannot open database at {path}: {exc}") from exc
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_aggregate("STDEV", 1, _StdDev)
    return conn


@contextmanager
def transaction(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Commit on success, roll back on any error, always close."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        logger.exception("Transaction rolled back")
        raise DatabaseError(str(exc)) from exc
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_query(sql: str, params: Sequence[Any] | dict | None = None,
              db_path: Path | str | None = None) -> pd.DataFrame:
    """Run a read query and return a DataFrame."""
    conn = get_connection(db_path)
    try:
        return pd.read_sql_query(sql, conn, params=params)
    except (sqlite3.Error, pd.errors.DatabaseError) as exc:
        raise DatabaseError(str(exc)) from exc
    finally:
        conn.close()


def execute(sql: str, params: Sequence[Any] | dict = (),
            db_path: Path | str | None = None) -> int:
    """Run one write statement in its own transaction; return rowcount."""
    with transaction(db_path) as conn:
        return conn.execute(sql, params).rowcount


def init_db(db_path: Path | str | None = None) -> None:
    """Create all tables, indexes and views from sql/schema.sql."""
    script = config.SCHEMA_FILE.read_text(encoding="utf-8")
    with transaction(db_path) as conn:
        conn.executescript(script)


def table_count(table: str, db_path: Path | str | None = None) -> int:
    """Row count for a known table (name is validated, not interpolated blindly)."""
    allowed = {"teams", "venues", "players", "series", "matches",
               "batting_performances", "bowling_performances",
               "fielding_performances", "player_career_stats"}
    if table not in allowed:
        raise ValueError(f"Unknown table: {table}")
    return int(run_query(f"SELECT COUNT(*) AS n FROM {table}", db_path=db_path)["n"][0])


_FORBIDDEN = ("insert", "update", "delete", "drop", "alter", "create", "replace",
              "attach", "detach", "pragma", "vacuum", "reindex")


def run_readonly(sql: str, db_path: Path | str | None = None, limit: int = 5000) -> pd.DataFrame:
    """Run user-typed SQL safely: single SELECT/WITH only, on a read-only connection."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise DatabaseError("Query is empty.")
    if ";" in cleaned:
        raise DatabaseError("Only one statement is allowed.")
    lowered = cleaned.lower()
    if not lowered.startswith(("select", "with")):
        raise DatabaseError("Only SELECT / WITH queries are allowed here.")
    words = set(__import__("re").findall(r"[a-z_]+", lowered))
    bad = words.intersection(_FORBIDDEN)
    if bad:
        raise DatabaseError(f"Statement not allowed in read-only mode: {', '.join(sorted(bad))}")
    path = Path(db_path or config.DB_PATH)
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.create_aggregate("STDEV", 1, _StdDev)
    try:
        return pd.read_sql_query(f"SELECT * FROM ({cleaned}) LIMIT {int(limit)}", conn)
    except (sqlite3.Error, pd.errors.DatabaseError) as exc:
        raise DatabaseError(str(exc)) from exc
    finally:
        conn.close()
