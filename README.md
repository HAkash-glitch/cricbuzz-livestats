# 🏏 Cricbuzz LiveStats — Real-Time Cricket Insights & SQL Analytics

A multi-page **Streamlit** app that combines the **Cricbuzz API** (via RapidAPI) with a **SQL database** to deliver
live scorecards, player leaderboards, 25 SQL analytics questions and a validated CRUD interface.

**Skills:** Python · SQL · Streamlit · JSON · REST API · pandas · Plotly

| Page | Purpose |
|---|---|
| Home | Overview, tools, instructions, live DB counts |
| Live Matches | Live / recent matches + full scorecards from the API; save recent matches to SQL |
| Top Player Stats | Most runs / wickets / best average / economy… by format, charted |
| SQL Analytics | The 25 brief questions (8 beginner, 8 intermediate, 9 advanced) + read-only custom SQL |
| CRUD Operations | Create / read / update / delete players, career stats and matches |

## ⚠️ Read this first: demo data vs. live data

This project was built **without a Cricbuzz API key**, so:

* The database ships with a **simulated sample dataset** (`services/seed_data.py`): real team and venue names,
  **fictional players**, simulated statistics. It exists so every page and all 25 queries work offline. **Do not treat any
  number in it as a real cricket record.**
* The Live Matches page uses a clearly-labelled **demo fixture** (`data/sample_live.json`) when no key is set.
* The API client (`api/cricbuzz_client.py`) is unit-tested with mocked HTTP (retry, errors, parsing) but its endpoint paths
  and response shapes were written from the RapidAPI listing and **have not been run against the live service**. When you
  add your key, expect to tweak a field name or two in the parsers; the tests show where.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env            # then paste your RapidAPI key (optional for demo mode)
streamlit run app.py
```
The first launch builds `data/cricbuzz.db` automatically. To rebuild it (and refresh the date-relative sample data):
`python -m services.seed_data [--dump]` (`--dump` regenerates `sql/sample_data.sql`).

### API key setup
1. Subscribe (free tier works) to **Cricbuzz Cricket** on RapidAPI: <https://rapidapi.com/cricketapilive/api/cricbuzz-cricket/>
2. Put the key in `.env` as `RAPIDAPI_KEY=...` (never commit `.env`; it is git-ignored).
3. Run `python check_api.py` to verify the key, then restart Streamlit. Home shows "RapidAPI key detected" and Live Matches defaults to the live feed.

### Documentation link
Set `DOCS_URL=` in `.env` to your GitHub repo/README URL; Home then shows a **Project documentation** button.

### Database setup
SQLite is used by default (zero setup). The schema is in `sql/schema.sql` (tables, constraints, 12 indexes, 2 views) and
sample rows in `sql/sample_data.sql`. All DB access is centralised in `utils/db_connection.py`; to move to MySQL/PostgreSQL
change `get_connection()` (and swap `AUTOINCREMENT`, `strftime`, `date('now')`, and the `STDEV` aggregate for the target
dialect's equivalents — the 25 queries are the main thing to port).

## Project structure
```
cricbuzz_livestats/
├── app.py                 Streamlit router + first-run DB bootstrap
├── config.py              env-based settings (no secrets in code)
├── requirements.txt  .env.example  .gitignore  .streamlit/config.toml (dark theme)
├── pages/                 home · live_matches · top_stats · sql_queries · crud_operations
├── api/cricbuzz_client.py REST client: headers, timeout, retry/backoff, pure JSON parsers
├── services/
│   ├── queries.py         the 25 SQL questions (SQL + notes + assumptions)
│   ├── crud_service.py    validated CRUD, transactions
│   ├── sync_service.py    API JSON -> SQL upserts (idempotent)
│   └── seed_data.py       deterministic sample-data generator
├── utils/                 db_connection.py (connections, transactions, read-only runner), ui.py
├── sql/                   schema.sql, sample_data.sql
├── data/                  cricbuzz.db (generated), demo JSON fixtures
├── tests/                 68 pytest tests (DB, all 25 queries, CRUD, API, every page)
├── notebooks/             data_fetching.ipynb (optional API → DB practice)
└── documentation/DESIGN.md  architecture, ER diagram, API→table map, checklist
```

## Tests
```bash
python -m pytest -q        # 68 tests: schema/constraints, each of the 25 queries, CRUD rules, API retry/parsing, UI smoke tests
```

## Notes on the 25 queries
Where the brief is ambiguous the choice is written next to the query on the SQL page (e.g. Q13/Q24 define a "partnership"
as the sum of two adjacent batters' scores, as the brief does; Q23's form thresholds are ours; Q19 adds a 10-innings
minimum so a standard deviation means something). `STDEV` is a custom aggregate registered in `db_connection.py`.

## Screenshots
Run the app and capture each page, then place the images in `documentation/` and link them here.

## Deliverable checklist (from the brief)
- [x] Source code — Streamlit app  - [x] DB schema + sample data  - [x] Setup & API-key docs  - [x] requirements.txt
- [x] Dashboard with all four modules  - [x] 25 SQL questions  - [x] PEP 8, docstrings, error handling, secrets in `.env`
- [ ] **Recording video** — yours to record (screen-capture a walkthrough of the five pages)
- [ ] **Git history** — run `git init` and commit as you go

## Future improvements
Auto-refresh live scores · full sync of players/series/venues from the API · player-vs-player comparison page ·
authentication on the CRUD page · Docker image + CI · PostgreSQL profile.
