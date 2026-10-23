"""Generate a realistic, deterministic SAMPLE dataset for offline use.

Team and venue names are real; player names are FICTIONAL and every statistic is
simulated. Run ``python -m services.seed_data`` to (re)build the database.
Real data arrives through ``services.sync_service`` once an API key is set.
"""
from __future__ import annotations

import argparse
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import config
from utils import db_connection as db

SEED = 2026
TEAMS = [("India", "IND"), ("Australia", "AUS"), ("England", "ENG"),
         ("South Africa", "RSA"), ("New Zealand", "NZ"), ("Pakistan", "PAK"),
         ("Sri Lanka", "SL"), ("Bangladesh", "BAN"), ("West Indies", "WI"),
         ("Afghanistan", "AFG")]
# (venue, city, country, capacity)
VENUES = [
    ("Narendra Modi Stadium", "Ahmedabad", "India", 132000),
    ("Eden Gardens", "Kolkata", "India", 66000),
    ("Wankhede Stadium", "Mumbai", "India", 33100),
    ("Melbourne Cricket Ground", "Melbourne", "Australia", 100024),
    ("Sydney Cricket Ground", "Sydney", "Australia", 48000),
    ("Lord's", "London", "England", 31100),
    ("The Oval", "London", "England", 27500),
    ("Wanderers Stadium", "Johannesburg", "South Africa", 34000),
    ("Newlands", "Cape Town", "South Africa", 25000),
    ("Eden Park", "Auckland", "New Zealand", 50000),
    ("National Stadium", "Karachi", "Pakistan", 34228),
    ("R. Premadasa Stadium", "Colombo", "Sri Lanka", 35000),
    ("Shere Bangla Stadium", "Dhaka", "Bangladesh", 26000),
    ("Kensington Oval", "Bridgetown", "West Indies", 28000),
    ("Sharjah Cricket Stadium", "Sharjah", "UAE", 16000),
    ("Dubai International Stadium", "Dubai", "UAE", 25000),
]
FIRST = ["Aarav", "Liam", "Noah", "Ethan", "Kabir", "Rohan", "Mason", "Jack", "Oscar", "Ravi",
         "Zane", "Idris", "Tariq", "Hamza", "Dev", "Callum", "Finn", "Arjun", "Leo", "Sami",
         "Yusuf", "Kyle", "Dane", "Rhys", "Imran", "Nuwan", "Tamim", "Jason", "Colin", "Hasan"]
LAST = ["Verma", "Walker", "Hughes", "Khan", "Perera", "Mitchell", "Nair", "Cooper", "Rahman",
        "Fraser", "Botha", "Ahmed", "Silva", "Bennett", "Reddy", "Holder", "Nabi", "Carter",
        "Joshi", "Murray", "Das", "Hayes", "Sharma", "Dixon", "Malik", "Ward", "Pillai", "Reid"]
BAT_STYLES = ["Right-hand bat", "Left-hand bat"]
BOWL_STYLES = ["Right-arm fast", "Right-arm medium", "Left-arm fast", "Right-arm offbreak",
               "Left-arm orthodox", "Legbreak googly"]
# squad template: (role, bat_skill-range, bowl_skill-range)
SQUAD = [("Batsman", (38, 55), (0, 0))] * 4 + [("Wicket-keeper", (30, 45), (0, 0))] + \
        [("All-rounder", (24, 36), (3, 6))] * 3 + [("Bowler", (8, 14), (6, 10))] * 3 + \
        [("Batsman", (28, 40), (0, 0))] + [("Wicket-keeper", (22, 30), (0, 0))] + \
        [("All-rounder", (20, 28), (3, 5))] + [("Bowler", (6, 10), (5, 8))]
FMT_BALLS = {"T20I": 120, "ODI": 300, "Test": 540}
FMT_SR = {"T20I": (120, 160), "ODI": (80, 105), "Test": (45, 62)}
FMT_SCALE = {"T20I": 0.55, "ODI": 0.9, "Test": 1.1}
FMT_BOWL_CAP = {"T20I": 24, "ODI": 60, "Test": 120}  # balls per bowler per innings


def _build_players(rng: random.Random, team_ids: dict[str, int], conn: sqlite3.Connection):
    used, players = set(), {}
    for team, tid in team_ids.items():
        squad = []
        for role, bat, bowl in SQUAD:
            while True:
                name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
                if name not in used:
                    used.add(name)
                    break
            bowl_style = rng.choice(BOWL_STYLES) if bowl[1] else None
            if role == "Wicket-keeper":
                bowl_style = None
            dob = date(1988, 1, 1) + timedelta(days=rng.randint(0, 365 * 13))
            cur = conn.execute(
                "INSERT INTO players(full_name,team_id,country,playing_role,batting_style,"
                "bowling_style,date_of_birth) VALUES (?,?,?,?,?,?,?)",
                (name, tid, team, role, rng.choice(BAT_STYLES), bowl_style, dob.isoformat()))
            squad.append({"id": cur.lastrowid, "role": role,
                          "bat": rng.uniform(*bat), "bowl": rng.uniform(*bowl) if bowl[1] else 0.0})
        players[tid] = squad
    return players


def _xi(squad):
    """Batting order: 4 bat, WK, 3 AR, 3 bowlers (first of each group)."""
    by = {"Batsman": [], "Wicket-keeper": [], "All-rounder": [], "Bowler": []}
    for p in squad:
        by[p["role"]].append(p)
    return by["Batsman"][:4] + by["Wicket-keeper"][:1] + by["All-rounder"][:3] + by["Bowler"][:3]


def _sim_innings(rng, xi, fmt, target=None, tough=1.0):
    """Return (batting rows, total, wickets_lost, balls_used)."""
    rows, total, outs, balls_used = [], 0, 0, 0
    cap = FMT_BALLS[fmt]
    for pos, p in enumerate(xi, start=1):
        if outs >= 10 or balls_used >= cap or (target is not None and total > target):
            break
        mean = max(2.0, p["bat"] * FMT_SCALE[fmt] * tough * (1.0 if pos <= 7 else 0.6))
        runs = int(min(rng.expovariate(1 / mean), 220))
        sr = rng.uniform(*FMT_SR[fmt]) * (0.85 if runs < 10 else 1.0)
        balls = max(1, int(round(runs * 100 / sr))) if runs else rng.randint(1, 8)
        is_out = 1 if rng.random() < 0.88 else 0
        if balls_used + balls >= cap:
            balls, is_out = max(1, cap - balls_used), 0
        if target is not None and total + runs > target:
            runs = target - total + 1
            balls, is_out = max(1, int(runs * 100 / sr)), 0
        total += runs
        balls_used += balls
        outs += is_out
        fours = min(runs // 6, int(runs * 0.55 / 4))
        sixes = min((runs - fours * 4) // 6, rng.randint(0, 1 + runs // 25)) if fmt != "Test" else 0
        rows.append(dict(pid=p["id"], pos=pos, runs=runs, balls=balls, fours=fours,
                         sixes=sixes, sr=round(runs * 100 / balls, 2), out=is_out))
    if rows and outs == 10:
        rows[-1]["out"] = 1
    return rows, total, outs, balls_used


def _sim_bowling(rng, fielders, fmt, runs_against, outs, balls_used):
    """Spread the opposition innings across the fielding side's bowlers."""
    bowlers = [p for p in fielders if p["role"] in ("Bowler", "All-rounder")]
    bowlers = sorted(bowlers, key=lambda p: -p["bowl"])[:6 if fmt == "Test" else 5]
    cap, remaining, spec = FMT_BOWL_CAP[fmt], balls_used, []
    for i, p in enumerate(bowlers):
        b = remaining if i == len(bowlers) - 1 else min(cap, remaining)
        b = min(b, cap * 2) if fmt == "Test" else min(b, cap)
        spec.append([p, b])
        remaining -= b
        if remaining <= 0:
            break
    spec = [s for s in spec if s[1] > 0]
    if remaining > 0 and spec:
        spec[0][1] += remaining
    tot_b = sum(b for _, b in spec) or 1
    weights = [max(0.1, p["bowl"]) for p, _ in spec]
    wk = [0] * len(spec)
    for _ in range(round(outs * 0.92)):
        wk[rng.choices(range(len(spec)), weights)[0]] += 1
    rows, left_runs = [], runs_against
    for i, (p, b) in enumerate(spec):
        r = left_runs if i == len(spec) - 1 else int(runs_against * b / tot_b * rng.uniform(.8, 1.2))
        r = max(0, min(r, left_runs))
        left_runs -= r
        ov = round(b / 6, 2)
        rows.append(dict(pid=p["id"], overs=ov, maidens=rng.randint(0, 2) if fmt != "T20I" else 0,
                         runs=r, wk=min(wk[i], 10), econ=round(r / ov, 2) if ov else 0.0))
    return rows


def _play_match(rng, conn, match_id, fmt, t1, t2, squads, toss_winner, toss_dec):
    xi = {t1: _xi(squads[t1]), t2: _xi(squads[t2])}
    bat_first = toss_winner if toss_dec == "bat" else (t2 if toss_winner == t1 else t1)
    field_first = t2 if bat_first == t1 else t1
    strength = {t: sum(p["bat"] for p in xi[t]) + 3 * sum(p["bowl"] for p in xi[t]) for t in (t1, t2)}
    plan = [(bat_first, field_first), (field_first, bat_first)]
    if fmt == "Test":
        plan += [(bat_first, field_first), (field_first, bat_first)]
    totals = {t1: 0, t2: 0}
    last = None
    for inn, (bat_t, bowl_t) in enumerate(plan, start=1):
        tough = (strength[bat_t] / ((strength[t1] + strength[t2]) / 2)) ** 1.3 * rng.uniform(0.85, 1.15)
        target = None
        if fmt != "Test" and inn == 2:
            target = totals[bowl_t]
        if fmt == "Test" and inn == 4:
            target = totals[bowl_t] - totals[bat_t]
        rows, total, outs, balls = _sim_innings(rng, xi[bat_t], fmt, target, tough)
        totals[bat_t] += total
        for r in rows:
            conn.execute("INSERT INTO batting_performances(match_id,player_id,innings_no,batting_position,"
                         "runs,balls_faced,fours,sixes,strike_rate,is_out) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (match_id, r["pid"], inn, r["pos"], r["runs"], r["balls"], r["fours"],
                          r["sixes"], r["sr"], r["out"]))
        for b in _sim_bowling(rng, xi[bowl_t], fmt, total, outs, balls):
            conn.execute("INSERT INTO bowling_performances(match_id,player_id,innings_no,overs,maidens,"
                         "runs_conceded,wickets,economy) VALUES (?,?,?,?,?,?,?,?)",
                         (match_id, b["pid"], inn, b["overs"], b["maidens"], b["runs"], b["wk"], b["econ"]))
        last = (bat_t, bowl_t, outs)
        # fielding credits: catches for ~70% of outs, stumpings ~6%
        for _ in range(outs):
            roll = rng.random()
            field = xi[bowl_t]
            if roll < 0.06:
                keeper = next(p for p in field if p["role"] == "Wicket-keeper")
                conn.execute("INSERT INTO fielding_performances VALUES (?,?,0,1) ON CONFLICT(match_id,player_id) "
                             "DO UPDATE SET stumpings=stumpings+1", (match_id, keeper["id"]))
            elif roll < 0.76:
                fp = rng.choice(field)
                conn.execute("INSERT INTO fielding_performances VALUES (?,?,1,0) ON CONFLICT(match_id,player_id) "
                             "DO UPDATE SET catches=catches+1", (match_id, fp["id"]))
    if totals[t1] == totals[t2]:
        return None, None, None
    winner = t1 if totals[t1] > totals[t2] else t2
    chased = last[0] == winner  # winner batted last
    if chased:
        return winner, max(1, 10 - last[2]), "wickets"
    return winner, abs(totals[t1] - totals[t2]), "runs"


def build(db_path: Path | str | None = None, matches_target: int = 560) -> None:
    """Rebuild the DB file and fill it with sample data."""
    path = Path(db_path or config.DB_PATH)
    if path.exists():
        path.unlink()
    db.init_db(path)
    rng = random.Random(SEED)
    today = date.today()
    with db.transaction(path) as conn:
        team_ids = {n: conn.execute("INSERT INTO teams(team_name,country,short_name) VALUES (?,?,?)",
                                    (n, n, s)).lastrowid for n, s in TEAMS}
        venue_ids = {}
        for name, city, country, cap in VENUES:
            venue_ids[(name, country)] = conn.execute(
                "INSERT INTO venues(venue_name,city,country,capacity) VALUES (?,?,?,?)",
                (name, city, country, cap)).lastrowid
        players = _build_players(rng, team_ids, conn)
        venues_by_country: dict[str, list[int]] = {}
        for (name, country), vid in venue_ids.items():
            venues_by_country.setdefault(country, []).append(vid)
        names = list(team_ids)

        # Series schedule: ~4 years of tours ending "now"; last two overlap the past 30 days.
        schedule, d = [], today - timedelta(days=1400)
        while d < today + timedelta(days=5):
            schedule.append(d)
            d += timedelta(days=rng.randint(9, 16))
        schedule[-1], schedule[-2] = today - timedelta(days=9), today - timedelta(days=24)
        n_played = 0
        for start in sorted(schedule):
            host, visitor = rng.sample(names, 2)
            fmt = rng.choices(["Test", "ODI", "T20I"], [0.22, 0.34, 0.44])[0]
            n = rng.randint(2, 4) if fmt == "Test" else rng.randint(3, 6)
            gap = 6 if fmt == "Test" else 3
            sid = conn.execute(
                "INSERT INTO series(series_name,host_country,match_type,start_date,total_matches) VALUES (?,?,?,?,?)",
                (f"{visitor} tour of {host} {start.year}", host, fmt, start.isoformat(), n)).lastrowid
            home_venues = venues_by_country.get(host) or venues_by_country["UAE"]
            for k in range(n):
                md = start + timedelta(days=k * gap)
                t1, t2 = team_ids[host], team_ids[visitor]
                if rng.random() < 0.25:                       # neutral-venue fixture
                    vid = rng.choice(venues_by_country["UAE"])
                else:
                    vid = rng.choice(home_venues)
                status = "Complete" if md < today else ("Live" if md == today else "Upcoming")
                toss_w = rng.choice([t1, t2])
                dec = "bat" if rng.random() < 0.45 else "bowl"
                mid = conn.execute(
                    "INSERT INTO matches(series_id,description,match_format,team1_id,team2_id,venue_id,"
                    "match_date,toss_winner_id,toss_decision,status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (sid, f"{k + 1}{'st' if k == 0 else 'nd' if k == 1 else 'rd' if k == 2 else 'th'} {fmt}",
                     fmt, t1, t2, vid, md.isoformat(), toss_w, dec, status)).lastrowid
                if status != "Complete":
                    continue
                winner, margin, vtype = _play_match(rng, conn, mid, fmt, t1, t2, players, toss_w, dec)
                if winner is None:
                    conn.execute("UPDATE matches SET status='No Result' WHERE match_id=?", (mid,))
                else:
                    conn.execute("UPDATE matches SET winner_id=?,victory_margin=?,victory_type=? WHERE match_id=?",
                                 (winner, margin, vtype, mid))
                n_played += 1
        _build_career_stats(rng, conn)
    print(f"Built {path} with {n_played} completed matches.")


def _build_career_stats(rng: random.Random, conn: sqlite3.Connection) -> None:
    """Career aggregates = recorded window x a veteran factor (pre-window history)."""
    rows = conn.execute("""
        SELECT p.player_id, m.match_format AS fmt,
               COUNT(DISTINCT m.match_id) AS matches, COUNT(b.perf_id) AS innings,
               SUM(b.runs) AS runs, MAX(b.runs) AS hs, SUM(b.is_out) AS outs,
               SUM(b.balls_faced) AS balls, SUM(b.runs>=100) AS c100,
               SUM(b.runs BETWEEN 50 AND 99) AS c50
        FROM players p JOIN batting_performances b ON b.player_id=p.player_id
        JOIN matches m ON m.match_id=b.match_id GROUP BY p.player_id, m.match_format""").fetchall()
    bowl = {(r["player_id"], r["fmt"]): r for r in conn.execute("""
        SELECT w.player_id, m.match_format AS fmt, SUM(w.wickets) AS wk, SUM(w.runs_conceded) AS rc,
               SUM(w.overs) AS ov FROM bowling_performances w JOIN matches m ON m.match_id=w.match_id
        GROUP BY w.player_id, m.match_format""")}
    field = {(r["player_id"], r["fmt"]): r for r in conn.execute("""
        SELECT f.player_id, m.match_format AS fmt, SUM(f.catches) AS ct, SUM(f.stumpings) AS st
        FROM fielding_performances f JOIN matches m ON m.match_id=f.match_id GROUP BY f.player_id, m.match_format""")}
    veteran = {}
    for r in rows:
        f = veteran.setdefault(r["player_id"], rng.uniform(1.0, 2.6))
        bw, fd = bowl.get((r["player_id"], r["fmt"])), field.get((r["player_id"], r["fmt"]))
        runs, inns, outs = int(r["runs"] * f), int(r["innings"] * f), max(1, int(r["outs"] * f))
        wk = int(bw["wk"] * f) if bw else 0
        conn.execute("INSERT INTO player_career_stats VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            r["player_id"], r["fmt"], int(r["matches"] * f), inns, runs,
            max(r["hs"], int(r["hs"] * rng.uniform(1.0, 1.25))), round(runs / outs, 2),
            round(r["runs"] * 100 / max(1, r["balls"]), 2), int(r["c100"] * f), int(r["c50"] * f),
            wk, round(bw["rc"] / bw["wk"], 2) if bw and bw["wk"] else None,
            round(bw["rc"] / bw["ov"], 2) if bw and bw["ov"] else None,
            int(fd["ct"] * f) if fd else 0, int(fd["st"] * f) if fd else 0))


def dump_sql(db_path: Path | str, out_file: Path | str) -> None:
    """Write INSERT-only sample data (schema lives in sql/schema.sql)."""
    conn = sqlite3.connect(db_path)
    with open(out_file, "w", encoding="utf-8") as fh:
        fh.write("-- Sample data for Cricbuzz LiveStats (simulated; fictional player names)\n")
        for line in conn.iterdump():
            if line.startswith("INSERT INTO"):
                fh.write(line + "\n")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dump", action="store_true", help="also write sql/sample_data.sql")
    args = ap.parse_args()
    build()
    if args.dump:
        dump_sql(config.DB_PATH, config.BASE_DIR / "sql" / "sample_data.sql")
