# Cricbuzz LiveStats — Design Notes

## 1. Architecture
```
 ┌──────────────────────────── Streamlit (pages/) ───────────────────────────┐
 │  Home   Live Matches   Top Stats   SQL Analytics   CRUD                    │
 └──────┬──────────┬───────────┬────────────┬────────────┬────────────────────┘
        │          │           │            │            │
        │     api/cricbuzz_client.py        │     services/crud_service.py (validation)
        │   (retry · timeout · parsers)     │     services/queries.py (25 SQL)
        │          │                        │            │
        │   services/sync_service.py ───────┴────────────┘
        │          │ upsert                       read / write
        └──────────▼──────────────────────────────────▼──────
                     utils/db_connection.py  (connect · transaction · read-only runner)
                                    │
                              SQLite  (sql/schema.sql)
 config.py + .env  →  keys, DB path, timeouts      utils/ui.py → theme, cache, charts
```
**Data flow:** API → `parse_*` (pure functions) → `sync_service` → SQL → `queries`/`crud_service` → pages.
Pages never build SQL from user text except the custom-SQL box, which is SELECT-only on a read-only connection.

## 2. ER diagram
```
teams 1──< players 1──< batting_performances >──1 matches >──1 venues
  │ 1           │ 1──< bowling_performances >──┘     │ >──1 series
  │ │           │ 1──< fielding_performances ─┘      │
  │ └──< matches (team1_id, team2_id, toss_winner_id, winner_id)
  └ players 1──< player_career_stats  (PK: player_id + match_format)
Views: v_match_details (matches + teams + venue + winner), v_player_profile
```
| Table | PK | Key FKs | Notable constraints |
|---|---|---|---|
| teams | team_id | — | UNIQUE name |
| venues | venue_id | — | capacity > 0, UNIQUE(name, city) |
| players | player_id | team_id → teams | role CHECK, UNIQUE(name, team) |
| series | series_id | — | match_type CHECK |
| matches | match_id | series, team1, team2, venue, toss_winner, winner | team1 ≠ team2, status/format/decision CHECKs |
| batting_performances | perf_id | match, player | UNIQUE(match, player, innings), position 1-11 |
| bowling_performances | perf_id | match, player | wickets 0-10, overs ≥ 0 |
| fielding_performances | (match, player) | match, player | — |
| player_career_stats | (player, format) | player | non-negative counters |

**Normalisation (3NF):** team/venue/series facts live once and are referenced by id; performances are separate fact
tables keyed by (match, player, innings). `player_career_stats` is a deliberate, documented *aggregate* table because the
stats API returns career totals that can't be rebuilt from the match rows we hold. Deletes: performances cascade from
player/match; `players.team_id` is RESTRICT so you can't orphan players by deleting a team.

## 3. Cricbuzz endpoints → tables (as written in the client; unverified live)
| Endpoint (`GET`, headers `X-RapidAPI-Key`, `X-RapidAPI-Host`) | Used for | Table(s) |
|---|---|---|
| `matches/v1/live`, `matches/v1/recent` | Live page; `sync_service.save_matches` | matches, teams, venues |
| `mcenter/v1/{id}/scard` | Scorecards | (displayed; batting/bowling_performances if persisted) |
| `stats/v1/topstats/0?statsType=…` | Top Stats API tab | (displayed) |
| `stats/v1/rankings/{category}` | rankings | player_career_stats (future) |
| `stats/v1/player/search`, `stats/v1/player/{id}` | player lookup | players |
| `teams/v1/international`, `series/v1/archives/international` | reference data | teams, series |

Rate limits depend on your RapidAPI plan; the client honours `Retry-After`, backs off exponentially on 429/5xx/timeouts
and surfaces a readable `ApiError` otherwise. Pages cache live calls for 30 s to protect the quota.

## 4. Requirements tracker
| Requirement | Status |
|---|---|
| API integration (requests, retry, errors) | ✅ built + mock-tested; ⚠️ not run against live API |
| SQL database, schema, indexes, views | ✅ |
| 25 SQL queries (easy/medium/hard) | ✅ all run; verified on sample data |
| Live Match page | ✅ (demo fixture without key) |
| Top Player Stats page | ✅ |
| SQL Queries & Analytics page | ✅ |
| CRUD page (players, stats, matches) | ✅ |
| Home page with docs/structure | ✅ |
| Secrets in env, PEP 8, docstrings, modular code | ✅ |
| Tests | ✅ 68 |
| Git version control | ⬜ yours: `git init` |
| Deployment (Streamlit Community Cloud) | ⬜ push repo, set `RAPIDAPI_KEY` in app secrets, entry `app.py` |
| Recording video | ⬜ yours |

## 5. Build order used (matches the mentor roadmap)
Environment → Database → API → CRUD → Analytics → Dashboard → Testing → Deployment.
