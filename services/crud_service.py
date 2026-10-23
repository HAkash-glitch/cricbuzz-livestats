"""CRUD for players, per-format career stats and matches, with validation.

All writes run inside ``db.transaction`` (commit / rollback). Validation errors
raise ``ValidationError`` with a user-readable message; DB errors raise
``DatabaseError``.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

import config
from utils import db_connection as db


class ValidationError(ValueError):
    """Invalid user input."""


@dataclass
class PlayerInput:
    full_name: str
    team_id: int
    playing_role: str
    batting_style: str | None = None
    bowling_style: str | None = None
    date_of_birth: str | None = None
    country: str | None = None

    def validate(self) -> None:
        name = (self.full_name or "").strip()
        if len(name) < 2:
            raise ValidationError("Full name must have at least 2 characters.")
        self.full_name = " ".join(name.split())
        if self.playing_role not in config.PLAYING_ROLES:
            raise ValidationError(f"Role must be one of {', '.join(config.PLAYING_ROLES)}.")
        if self.date_of_birth:
            try:
                dob = date.fromisoformat(self.date_of_birth)
            except ValueError as exc:
                raise ValidationError("Date of birth must be YYYY-MM-DD.") from exc
            if not date(1940, 1, 1) <= dob <= date.today():
                raise ValidationError("Date of birth is out of range.")


@dataclass
class CareerStatInput:
    player_id: int
    match_format: str
    matches: int = 0
    innings: int = 0
    runs: int = 0
    highest_score: int = 0
    batting_avg: float | None = None
    strike_rate: float | None = None
    centuries: int = 0
    fifties: int = 0
    wickets: int = 0
    bowling_avg: float | None = None
    economy: float | None = None
    catches: int = 0
    stumpings: int = 0
    _ints: tuple = field(default=("matches", "innings", "runs", "highest_score", "centuries",
                                  "fifties", "wickets", "catches", "stumpings"), repr=False)

    def validate(self) -> None:
        if self.match_format not in config.FORMATS:
            raise ValidationError("Format must be Test, ODI or T20I.")
        for f in self._ints:
            if getattr(self, f) < 0:
                raise ValidationError(f"{f.replace('_', ' ').title()} cannot be negative.")
        if self.innings > self.matches * 2 and self.match_format == "Test" or \
                (self.match_format != "Test" and self.innings > self.matches):
            raise ValidationError("Innings cannot exceed matches played (x2 for Tests).")
        if self.highest_score > self.runs:
            raise ValidationError("Highest score cannot exceed total runs.")
        for f in ("batting_avg", "strike_rate", "bowling_avg", "economy"):
            v = getattr(self, f)
            if v is not None and v < 0:
                raise ValidationError(f"{f.replace('_', ' ').title()} cannot be negative.")


# ------------------------------------------------------------- lookups
def list_teams(db_path=None) -> pd.DataFrame:
    return db.run_query("SELECT team_id, team_name FROM teams ORDER BY team_name", db_path=db_path)


def list_venues(db_path=None) -> pd.DataFrame:
    return db.run_query("SELECT venue_id, venue_name || ', ' || city AS label FROM venues ORDER BY venue_name",
                        db_path=db_path)


# ------------------------------------------------------------- players
def list_players(search: str = "", team_id: int | None = None, role: str | None = None,
                 db_path=None) -> pd.DataFrame:
    sql = ("SELECT p.player_id, p.full_name, t.team_name, p.playing_role, p.batting_style, "
           "p.bowling_style, p.date_of_birth FROM players p JOIN teams t ON t.team_id = p.team_id WHERE 1=1")
    params: list[Any] = []
    if search.strip():
        sql += " AND p.full_name LIKE ?"
        params.append(f"%{search.strip()}%")
    if team_id:
        sql += " AND p.team_id = ?"
        params.append(team_id)
    if role:
        sql += " AND p.playing_role = ?"
        params.append(role)
    return db.run_query(sql + " ORDER BY p.full_name", params, db_path)


def get_player(player_id: int, db_path=None) -> dict[str, Any] | None:
    df = db.run_query("SELECT * FROM players WHERE player_id = ?", [player_id], db_path)
    return None if df.empty else df.iloc[0].to_dict()


def create_player(p: PlayerInput, db_path=None) -> int:
    p.validate()
    with db.transaction(db_path) as conn:
        country = p.country or conn.execute("SELECT country FROM teams WHERE team_id=?", (p.team_id,)).fetchone()
        if country is None:
            raise ValidationError("Selected team does not exist.")
        country = p.country or country[0]
        try:
            return conn.execute(
                "INSERT INTO players(full_name,team_id,country,playing_role,batting_style,bowling_style,date_of_birth)"
                " VALUES (?,?,?,?,?,?,?)",
                (p.full_name, p.team_id, country, p.playing_role, p.batting_style or None,
                 p.bowling_style or None, p.date_of_birth or None)).lastrowid
        except sqlite3.IntegrityError as exc:
            raise ValidationError(f"{p.full_name} already exists in that team.") from exc


def update_player(player_id: int, p: PlayerInput, db_path=None) -> bool:
    p.validate()
    with db.transaction(db_path) as conn:
        try:
            cur = conn.execute(
                "UPDATE players SET full_name=?, team_id=?, playing_role=?, batting_style=?, bowling_style=?,"
                " date_of_birth=? WHERE player_id=?",
                (p.full_name, p.team_id, p.playing_role, p.batting_style or None, p.bowling_style or None,
                 p.date_of_birth or None, player_id))
        except sqlite3.IntegrityError as exc:
            raise ValidationError(f"Cannot update: {exc}") from exc
        return cur.rowcount > 0


def delete_player(player_id: int, db_path=None) -> bool:
    """Delete a player; cascades to their stats rows (ON DELETE CASCADE)."""
    with db.transaction(db_path) as conn:
        return conn.execute("DELETE FROM players WHERE player_id=?", (player_id,)).rowcount > 0


# ------------------------------------------------------------- career stats
def get_career_stats(player_id: int, db_path=None) -> pd.DataFrame:
    return db.run_query("SELECT * FROM player_career_stats WHERE player_id=? ORDER BY match_format",
                        [player_id], db_path)


def upsert_career_stat(s: CareerStatInput, db_path=None) -> None:
    s.validate()
    cols = ["player_id", "match_format", "matches", "innings", "runs", "highest_score", "batting_avg",
            "strike_rate", "centuries", "fifties", "wickets", "bowling_avg", "economy", "catches", "stumpings"]
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols[2:])
    with db.transaction(db_path) as conn:
        if conn.execute("SELECT 1 FROM players WHERE player_id=?", (s.player_id,)).fetchone() is None:
            raise ValidationError("Player does not exist.")
        conn.execute(f"INSERT INTO player_career_stats({','.join(cols)}) VALUES ({','.join('?' * len(cols))}) "
                     f"ON CONFLICT(player_id, match_format) DO UPDATE SET {updates}",
                     [getattr(s, c) for c in cols])


def delete_career_stat(player_id: int, match_format: str, db_path=None) -> bool:
    with db.transaction(db_path) as conn:
        return conn.execute("DELETE FROM player_career_stats WHERE player_id=? AND match_format=?",
                            (player_id, match_format)).rowcount > 0


# ------------------------------------------------------------- matches
def list_matches(limit: int = 50, db_path=None) -> pd.DataFrame:
    return db.run_query(
        "SELECT match_id, match_date, description, match_format, team1, team2, venue_name, status, winner, "
        "victory_margin, victory_type FROM v_match_details ORDER BY match_date DESC, match_id DESC LIMIT ?",
        [limit], db_path)


def create_match(description: str, fmt: str, team1_id: int, team2_id: int, venue_id: int, match_date: str,
                 status: str = "Upcoming", db_path=None) -> int:
    if not description.strip():
        raise ValidationError("Description is required.")
    if fmt not in config.FORMATS:
        raise ValidationError("Invalid format.")
    if team1_id == team2_id:
        raise ValidationError("A team cannot play itself.")
    try:
        date.fromisoformat(match_date)
    except ValueError as exc:
        raise ValidationError("Match date must be YYYY-MM-DD.") from exc
    with db.transaction(db_path) as conn:
        return conn.execute(
            "INSERT INTO matches(description,match_format,team1_id,team2_id,venue_id,match_date,status)"
            " VALUES (?,?,?,?,?,?,?)",
            (description.strip(), fmt, team1_id, team2_id, venue_id, match_date, status)).lastrowid


def record_result(match_id: int, winner_id: int | None, margin: int | None, vtype: str | None,
                  db_path=None) -> bool:
    """Set a match result (winner must be one of the two teams)."""
    if winner_id is not None and (margin is None or margin < 0 or vtype not in ("runs", "wickets")):
        raise ValidationError("A winner needs a non-negative margin and a type (runs / wickets).")
    with db.transaction(db_path) as conn:
        row = conn.execute("SELECT team1_id, team2_id FROM matches WHERE match_id=?", (match_id,)).fetchone()
        if row is None:
            return False
        if winner_id is not None and winner_id not in (row[0], row[1]):
            raise ValidationError("Winner must be one of the two teams in the match.")
        conn.execute("UPDATE matches SET winner_id=?, victory_margin=?, victory_type=?, status=? WHERE match_id=?",
                     (winner_id, margin if winner_id else None, vtype if winner_id else None,
                      "Complete" if winner_id else "No Result", match_id))
        return True


def delete_match(match_id: int, db_path=None) -> bool:
    with db.transaction(db_path) as conn:
        return conn.execute("DELETE FROM matches WHERE match_id=?", (match_id,)).rowcount > 0
