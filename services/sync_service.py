"""Persist Cricbuzz API data into the SQL database (idempotent upserts)."""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

from api.cricbuzz_client import CricbuzzClient, parse_match_list
from utils import db_connection as db

logger = logging.getLogger(__name__)


def _team(conn: sqlite3.Connection, cb_id: int | None, name: str, short: str | None) -> int:
    row = conn.execute("SELECT team_id FROM teams WHERE cb_team_id=? OR team_name=?", (cb_id, name)).fetchone()
    if row:
        conn.execute("UPDATE teams SET cb_team_id=COALESCE(cb_team_id,?) WHERE team_id=?", (cb_id, row[0]))
        return row[0]
    return conn.execute("INSERT INTO teams(cb_team_id,team_name,country,short_name) VALUES (?,?,?,?)",
                        (cb_id, name, name, short)).lastrowid


def _venue(conn: sqlite3.Connection, cb_id: int | None, name: str, city: str) -> int:
    row = conn.execute("SELECT venue_id FROM venues WHERE cb_venue_id=? OR (venue_name=? AND city=?)",
                       (cb_id, name, city)).fetchone()
    if row:
        return row[0]
    return conn.execute("INSERT INTO venues(cb_venue_id,venue_name,city,country) VALUES (?,?,?,?)",
                        (cb_id, name, city, "Unknown")).lastrowid


def save_matches(matches: list[dict[str, Any]], db_path=None) -> int:
    """Upsert parsed matches (see parse_match_list). Returns rows written."""
    written = 0
    with db.transaction(db_path) as conn:
        for m in matches:
            if not (m.get("match_id") and m.get("team1") and m.get("team2") and m.get("date")
                    and m.get("format") in ("Test", "ODI", "T20I") and m.get("venue")):
                continue  # incomplete record (e.g. non-international format) - skip, don't crash
            t1 = _team(conn, m["team1_id"], m["team1"], m["team1_short"])
            t2 = _team(conn, m["team2_id"], m["team2"], m["team2_short"])
            if t1 == t2:
                continue
            v = _venue(conn, m["venue_id"], m["venue"], m.get("city") or "")
            state = (m.get("state") or "").lower()
            status = "Live" if state in ("in progress", "live") else "Upcoming" if state == "preview" else "Complete"
            conn.execute(
                "INSERT INTO matches(cb_match_id,description,match_format,team1_id,team2_id,venue_id,match_date,status) "
                "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(cb_match_id) DO UPDATE SET status=excluded.status",
                (m["match_id"], m.get("description") or m["series"] or "Match", m["format"], t1, t2, v, m["date"], status))
            written += 1
    return written


def sync_recent_matches(client: CricbuzzClient, db_path=None) -> int:
    """Fetch recent matches from the API and store them. Raises ApiError/DatabaseError."""
    return save_matches(parse_match_list(client.recent_matches()), db_path)
