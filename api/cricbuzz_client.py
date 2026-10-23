"""Thin Cricbuzz (RapidAPI) client: auth headers, timeout, retry/backoff, parsing.

Endpoint paths follow the public RapidAPI "cricbuzz-cricket" listing. They were
written from that documentation and have NOT been exercised against the live
service in this build (no API key / network). Parsers are defensive for that reason.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import requests

import config

logger = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}
FORMAT_MAP = {"TEST": "Test", "ODI": "ODI", "T20": "T20I", "T20I": "T20I"}


class ApiError(Exception):
    """Any failure talking to the Cricbuzz API (network, HTTP, bad JSON, no key)."""


class CricbuzzClient:
    """Wraps requests.Session with retries. Inject ``session`` in tests."""

    def __init__(self, api_key: str | None = None, host: str | None = None,
                 session: requests.Session | None = None,
                 max_retries: int | None = None, backoff: float = 1.0) -> None:
        self.api_key = (api_key if api_key is not None else config.RAPIDAPI_KEY).strip()
        self.host = host or config.RAPIDAPI_HOST
        self.base_url = f"https://{self.host}"
        self.session = session or requests.Session()
        self.max_retries = config.API_MAX_RETRIES if max_retries is None else max_retries
        self.backoff = backoff

    @property
    def headers(self) -> dict[str, str]:
        return {"X-RapidAPI-Key": self.api_key, "X-RapidAPI-Host": self.host}

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET ``path`` and return parsed JSON; retry transient failures."""
        if not self.api_key:
            raise ApiError("RAPIDAPI_KEY is not set. Add it to .env (see README).")
        url = f"{self.base_url}/{path.lstrip('/')}"
        last: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.get(url, headers=self.headers, params=params,
                                        timeout=config.API_TIMEOUT_SECONDS)
                if resp.status_code in RETRY_STATUS and attempt < self.max_retries:
                    wait = float(resp.headers.get("Retry-After", self.backoff * 2 ** attempt))
                    logger.warning("HTTP %s from %s, retry in %.1fs", resp.status_code, path, wait)
                    time.sleep(min(wait, 30))
                    continue
                if resp.status_code in (401, 403):
                    raise ApiError("API key rejected (HTTP %s). Check RAPIDAPI_KEY / subscription." % resp.status_code)
                if resp.status_code == 429:
                    raise ApiError("Rate limit reached (HTTP 429). Try again later.")
                resp.raise_for_status()
                try:
                    return resp.json()
                except ValueError as exc:
                    raise ApiError(f"Invalid JSON from {path}") from exc
            except (requests.ConnectionError, requests.Timeout) as exc:
                last = exc
                if attempt < self.max_retries:
                    time.sleep(self.backoff * 2 ** attempt)
                    continue
            except requests.HTTPError as exc:
                raise ApiError(f"HTTP error from {path}: {exc}") from exc
        raise ApiError(f"Network failure for {path} after {self.max_retries + 1} tries: {last}")

    # ---- endpoints ------------------------------------------------------
    def live_matches(self) -> dict[str, Any]:
        return self.get("matches/v1/live")

    def recent_matches(self) -> dict[str, Any]:
        return self.get("matches/v1/recent")

    def scorecard(self, match_id: int) -> dict[str, Any]:
        return self.get(f"mcenter/v1/{match_id}/scard")

    def top_stats(self, stats_type: str = "mostRuns", format_type: str | None = None) -> dict[str, Any]:
        params = {"statsType": stats_type}
        if format_type:
            params["matchType"] = format_type
        return self.get("stats/v1/topstats/0", params)

    def rankings(self, category: str = "batsmen", format_type: str = "odi") -> dict[str, Any]:
        return self.get(f"stats/v1/rankings/{category}", {"formatType": format_type})

    def player_search(self, name: str) -> dict[str, Any]:
        return self.get("stats/v1/player/search", {"plrN": name})

    def player_info(self, player_id: int) -> dict[str, Any]:
        return self.get(f"stats/v1/player/{player_id}")

    def international_teams(self) -> dict[str, Any]:
        return self.get("teams/v1/international")

    def series_archives(self) -> dict[str, Any]:
        return self.get("series/v1/archives/international")


# ---- parsing helpers (pure functions, unit-tested) ------------------------
def _ms_to_date(ms: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _score_text(score: dict[str, Any] | None) -> str:
    """Turn {'inngs1': {'runs':250,'wickets':6,'overs':50}} into '250/6 (50 ov)'."""
    if not score:
        return ""
    parts = []
    for key in sorted(k for k in score if k.startswith("inngs")):
        i = score[key]
        w = i.get("wickets", 10)
        wtxt = "" if w == 10 else f"/{w}"
        parts.append(f"{i.get('runs', 0)}{wtxt} ({i.get('overs', '?')} ov)")
    return " & ".join(parts)


def parse_match_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten typeMatches -> seriesMatches -> matches into simple dicts."""
    out: list[dict[str, Any]] = []
    for tm in payload.get("typeMatches", []) or []:
        for sm in tm.get("seriesMatches", []) or []:
            wrap = sm.get("seriesAdWrapper") or {}
            for m in wrap.get("matches", []) or []:
                info, score = m.get("matchInfo", {}), m.get("matchScore", {})
                t1, t2, venue = info.get("team1", {}), info.get("team2", {}), info.get("venueInfo", {})
                out.append({
                    "match_id": info.get("matchId"),
                    "series_id": info.get("seriesId"),
                    "series": info.get("seriesName") or wrap.get("seriesName"),
                    "description": info.get("matchDesc"),
                    "format": FORMAT_MAP.get(str(info.get("matchFormat", "")).upper(), info.get("matchFormat")),
                    "state": info.get("state"),
                    "status": info.get("status"),
                    "date": _ms_to_date(info.get("startDate")),
                    "team1_id": t1.get("teamId"), "team1": t1.get("teamName"), "team1_short": t1.get("teamSName"),
                    "team2_id": t2.get("teamId"), "team2": t2.get("teamName"), "team2_short": t2.get("teamSName"),
                    "venue_id": venue.get("id"), "venue": venue.get("ground"), "city": venue.get("city"),
                    "team1_score": _score_text(score.get("team1Score")),
                    "team2_score": _score_text(score.get("team2Score")),
                })
    return out


def parse_scorecard(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one dict per innings with 'batting' and 'bowling' row lists."""
    innings = []
    for inn in payload.get("scoreCard", []) or []:
        bat = inn.get("batTeamDetails", {})
        bowl = inn.get("bowlTeamDetails", {})
        sd = inn.get("scoreDetails", {})
        innings.append({
            "team": bat.get("batTeamName"),
            "total": f"{sd.get('runs', 0)}/{sd.get('wickets', 0)} ({sd.get('overs', '?')} ov)",
            "batting": [{"Batter": b.get("batName"), "R": b.get("runs"), "B": b.get("balls"),
                         "4s": b.get("fours"), "6s": b.get("sixes"), "SR": b.get("strikeRate", b.get("strkRate")),
                         "Dismissal": b.get("outDesc")}
                        for b in (bat.get("batsmenData") or {}).values()],
            "bowling": [{"Bowler": b.get("bowlName"), "O": b.get("overs"), "M": b.get("maidens"),
                         "R": b.get("runs"), "W": b.get("wickets"), "Econ": b.get("economy")}
                        for b in (bowl.get("bowlersData") or {}).values()],
        })
    return innings


def parse_top_stats(payload: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    """Parse the {'headers': [...], 'values': [{'values': [...]}, ...]} table shape."""
    headers = payload.get("headers") or []
    rows = [r.get("values", []) for r in payload.get("values", []) or []]
    return headers, rows
