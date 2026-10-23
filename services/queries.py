"""The 25 SQL practice questions from the project brief.

Each entry: id, level, title, question, sql, concepts, notes (assumptions),
and optionally ``extra`` (title, sql) for follow-up result tables.
Dialect: SQLite (window functions, CTEs). ``date('now')`` is "today".
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from utils import db_connection as db

# Shared CTE text used by several queries (one row per team per decided match).
_TEAM_MATCHES = """
tm AS (
    SELECT team1_id AS team_id, team1_country AS team_country, venue_country,
           CASE WHEN winner_id = team1_id THEN 1 ELSE 0 END AS won
    FROM v_match_details WHERE status = 'Complete' AND winner_id IS NOT NULL
    UNION ALL
    SELECT team2_id, team2_country, venue_country,
           CASE WHEN winner_id = team2_id THEN 1 ELSE 0 END
    FROM v_match_details WHERE status = 'Complete' AND winner_id IS NOT NULL
)"""

QUERIES: list[dict[str, Any]] = [
 # ------------------------------------------------------------ BEGINNER
 dict(id=1, level="Beginner", title="Indian players",
      question="Find all players who represent India: full name, playing role, batting style, bowling style.",
      concepts="SELECT, WHERE",
      sql="""SELECT full_name, playing_role, batting_style, bowling_style
FROM players
WHERE country = 'India'
ORDER BY full_name""", notes=""),
 dict(id=2, level="Beginner", title="Matches in the last 30 days",
      question="Matches played in the last 30 days with description, both teams, venue + city, date; newest first.",
      concepts="WHERE with date arithmetic, ORDER BY, view join",
      sql="""SELECT description, team1, team2, venue_name || ', ' || city AS venue, match_date
FROM v_match_details
WHERE match_date BETWEEN date('now', '-30 day') AND date('now')
  AND status <> 'Upcoming'
ORDER BY match_date DESC""", notes="Relative to today's date, so the result changes daily."),
 dict(id=3, level="Beginner", title="Top 10 ODI run scorers",
      question="Top 10 ODI run scorers: name, total runs, batting average, centuries.",
      concepts="JOIN, ORDER BY, LIMIT",
      sql="""SELECT p.full_name, c.runs AS total_runs, c.batting_avg, c.centuries
FROM player_career_stats c
JOIN players p ON p.player_id = c.player_id
WHERE c.match_format = 'ODI'
ORDER BY c.runs DESC
LIMIT 10""", notes=""),
 dict(id=4, level="Beginner", title="Large venues",
      question="Venues with capacity above 50,000: name, city, country, capacity, largest first.",
      concepts="WHERE, ORDER BY",
      sql="""SELECT venue_name, city, country, capacity
FROM venues
WHERE capacity > 50000
ORDER BY capacity DESC""", notes=""),
 dict(id=5, level="Beginner", title="Wins per team",
      question="How many matches has each team won? Most wins first.",
      concepts="JOIN, GROUP BY, COUNT",
      sql="""SELECT t.team_name, COUNT(*) AS total_wins
FROM matches m
JOIN teams t ON t.team_id = m.winner_id
GROUP BY t.team_name
ORDER BY total_wins DESC""", notes="Matches without a winner (no result) are excluded by the inner join."),
 dict(id=6, level="Beginner", title="Players per role",
      question="Count how many players belong to each playing role.",
      concepts="GROUP BY, COUNT",
      sql="""SELECT playing_role, COUNT(*) AS player_count
FROM players
GROUP BY playing_role
ORDER BY player_count DESC""", notes=""),
 dict(id=7, level="Beginner", title="Highest score per format",
      question="Highest individual batting score in each format (Test, ODI, T20I).",
      concepts="GROUP BY, MAX",
      sql="""SELECT match_format, MAX(highest_score) AS highest_score
FROM player_career_stats
GROUP BY match_format
ORDER BY highest_score DESC""", notes=""),
 dict(id=8, level="Beginner", title="Series starting in 2024",
      question="All series that started in 2024: name, host country, match type, start date, matches planned.",
      concepts="strftime date part, WHERE",
      sql="""SELECT series_name, host_country, match_type, start_date, total_matches
FROM series
WHERE strftime('%Y', start_date) = '2024'
ORDER BY start_date""", notes=""),
 # ------------------------------------------------------------ INTERMEDIATE
 dict(id=9, level="Intermediate", title="Genuine all-rounders",
      question="All-rounders with more than 1000 runs AND more than 50 wickets: name, runs, wickets, format.",
      concepts="JOIN, GROUP BY, HAVING, GROUP_CONCAT",
      sql="""SELECT p.full_name, SUM(c.runs) AS total_runs, SUM(c.wickets) AS total_wickets,
       GROUP_CONCAT(c.match_format, ', ') AS formats
FROM player_career_stats c
JOIN players p ON p.player_id = c.player_id
WHERE p.playing_role = 'All-rounder'
GROUP BY p.player_id, p.full_name
HAVING SUM(c.runs) > 1000 AND SUM(c.wickets) > 50
ORDER BY total_runs DESC""",
      notes="Totals are summed across formats; the formats column lists every format the player appears in."),
 dict(id=10, level="Intermediate", title="Last 20 completed matches",
      question="Last 20 completed matches: description, teams, winner, margin, victory type, venue.",
      concepts="View, ORDER BY, LIMIT",
      sql="""SELECT description, team1, team2, winner, victory_margin, victory_type, venue_name, match_date
FROM v_match_details
WHERE status = 'Complete' AND winner IS NOT NULL
ORDER BY match_date DESC, match_id DESC
LIMIT 20""", notes=""),
 dict(id=11, level="Intermediate", title="Cross-format comparison",
      question="Players who played >= 2 formats: runs in Test / ODI / T20I and overall batting average.",
      concepts="Conditional aggregation (pivot), HAVING",
      sql="""SELECT p.full_name,
       SUM(CASE WHEN c.match_format = 'Test' THEN c.runs ELSE 0 END) AS test_runs,
       SUM(CASE WHEN c.match_format = 'ODI'  THEN c.runs ELSE 0 END) AS odi_runs,
       SUM(CASE WHEN c.match_format = 'T20I' THEN c.runs ELSE 0 END) AS t20i_runs,
       ROUND(SUM(c.runs) * 1.0 / SUM(c.runs * 1.0 / NULLIF(c.batting_avg, 0)), 2) AS overall_batting_avg
FROM player_career_stats c
JOIN players p ON p.player_id = c.player_id
GROUP BY p.player_id, p.full_name
HAVING COUNT(DISTINCT c.match_format) >= 2
ORDER BY overall_batting_avg DESC""",
      notes="Overall average = total runs / total dismissals, with dismissals recovered as runs / format average."),
 dict(id=12, level="Intermediate", title="Home vs away record",
      question="Each team's wins at home vs away (home = venue country equals team country).",
      concepts="CTE, UNION ALL, conditional aggregation",
      sql="WITH " + _TEAM_MATCHES + """
SELECT t.team_name,
       SUM(CASE WHEN tm.venue_country =  tm.team_country THEN 1   ELSE 0 END) AS home_matches,
       SUM(CASE WHEN tm.venue_country =  tm.team_country THEN tm.won ELSE 0 END) AS home_wins,
       SUM(CASE WHEN tm.venue_country <> tm.team_country THEN 1   ELSE 0 END) AS away_matches,
       SUM(CASE WHEN tm.venue_country <> tm.team_country THEN tm.won ELSE 0 END) AS away_wins
FROM tm JOIN teams t ON t.team_id = tm.team_id
GROUP BY t.team_name
ORDER BY home_wins + away_wins DESC""", notes="Neutral venues (e.g. UAE) count as away for both teams."),
 dict(id=13, level="Intermediate", title="100+ partnerships",
      question="Consecutive batters (adjacent positions) with a combined 100+ in the same innings.",
      concepts="Self-join, derived column",
      sql="""SELECT p1.full_name AS batter_1, p2.full_name AS batter_2,
       b1.runs + b2.runs AS combined_runs,
       m.description || ' (' || m.match_date || ')' AS match,
       b1.innings_no
FROM batting_performances b1
JOIN batting_performances b2
  ON b2.match_id = b1.match_id AND b2.innings_no = b1.innings_no
 AND b2.batting_position = b1.batting_position + 1
JOIN players p1 ON p1.player_id = b1.player_id
JOIN players p2 ON p2.player_id = b2.player_id
JOIN matches m  ON m.match_id = b1.match_id
WHERE b1.runs + b2.runs >= 100
ORDER BY combined_runs DESC
LIMIT 100""", notes="Ball-by-ball partnership data isn't in scope, so partnership = sum of the two adjacent batters' scores (as the brief defines)."),
 dict(id=14, level="Intermediate", title="Bowling at venues",
      question="Bowlers with >= 3 matches at a venue (4+ overs each): avg economy, wickets, matches.",
      concepts="Row filter before GROUP BY, HAVING COUNT(DISTINCT)",
      sql="""SELECT p.full_name, v.venue_name,
       ROUND(AVG(w.economy), 2) AS avg_economy,
       SUM(w.wickets) AS total_wickets,
       COUNT(DISTINCT w.match_id) AS matches_played
FROM bowling_performances w
JOIN players p ON p.player_id = w.player_id
JOIN matches m ON m.match_id = w.match_id
JOIN venues  v ON v.venue_id = m.venue_id
WHERE w.overs >= 4
GROUP BY p.player_id, p.full_name, v.venue_id, v.venue_name
HAVING COUNT(DISTINCT w.match_id) >= 3
ORDER BY avg_economy ASC""", notes=""),
 dict(id=15, level="Intermediate", title="Performance in close matches",
      question="Close match = won by < 50 runs OR < 5 wickets. Per batter: avg runs, close matches, how many their team won.",
      concepts="CASE in WHERE, subquery-free aggregation",
      sql="""SELECT p.full_name,
       ROUND(AVG(b.runs), 2) AS avg_runs,
       COUNT(DISTINCT m.match_id) AS close_matches,
       COUNT(DISTINCT CASE WHEN m.winner_id = p.team_id THEN m.match_id END) AS team_wins
FROM batting_performances b
JOIN matches m ON m.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
WHERE (m.victory_type = 'runs'    AND m.victory_margin < 50)
   OR (m.victory_type = 'wickets' AND m.victory_margin < 5)
GROUP BY p.player_id, p.full_name
ORDER BY avg_runs DESC
LIMIT 50""", notes="Top 50 shown. A player's side is taken from players.team_id."),
 dict(id=16, level="Intermediate", title="Year-by-year batting",
      question="Since 2020: per player per year, avg runs per match and avg strike rate (>= 5 matches that year).",
      concepts="strftime, GROUP BY two keys, HAVING",
      sql="""SELECT p.full_name, strftime('%Y', m.match_date) AS year,
       ROUND(SUM(b.runs) * 1.0 / COUNT(DISTINCT m.match_id), 2) AS avg_runs_per_match,
       ROUND(AVG(b.strike_rate), 2) AS avg_strike_rate,
       COUNT(DISTINCT m.match_id) AS matches
FROM batting_performances b
JOIN matches m ON m.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
WHERE m.match_date >= '2020-01-01'
GROUP BY p.player_id, p.full_name, year
HAVING COUNT(DISTINCT m.match_id) >= 5
ORDER BY p.full_name, year""", notes=""),
 # ------------------------------------------------------------ ADVANCED
 dict(id=17, level="Advanced", title="Does winning the toss help?",
      question="% of matches won by the toss winner, split by their toss decision.",
      concepts="Conditional aggregation, ratio",
      sql="""SELECT toss_decision,
       COUNT(*) AS matches,
       SUM(CASE WHEN toss_winner_id = winner_id THEN 1 ELSE 0 END) AS toss_winner_won,
       ROUND(100.0 * SUM(CASE WHEN toss_winner_id = winner_id THEN 1 ELSE 0 END) / COUNT(*), 2) AS win_pct
FROM matches
WHERE status = 'Complete' AND winner_id IS NOT NULL AND toss_winner_id IS NOT NULL
GROUP BY toss_decision
UNION ALL
SELECT 'ALL', COUNT(*),
       SUM(CASE WHEN toss_winner_id = winner_id THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN toss_winner_id = winner_id THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM matches
WHERE status = 'Complete' AND winner_id IS NOT NULL AND toss_winner_id IS NOT NULL""", notes=""),
 dict(id=18, level="Advanced", title="Most economical limited-overs bowlers",
      question="ODI+T20I bowlers: overall economy and wickets; >= 10 matches and >= 2 overs per match on average.",
      concepts="Weighted aggregate, HAVING on derived average",
      sql="""SELECT p.full_name,
       ROUND(SUM(w.runs_conceded) * 1.0 / SUM(w.overs), 2) AS economy_rate,
       SUM(w.wickets) AS total_wickets,
       COUNT(DISTINCT w.match_id) AS matches
FROM bowling_performances w
JOIN matches m ON m.match_id = w.match_id
JOIN players p ON p.player_id = w.player_id
WHERE m.match_format IN ('ODI', 'T20I')
GROUP BY p.player_id, p.full_name
HAVING COUNT(DISTINCT w.match_id) >= 10
   AND SUM(w.overs) * 1.0 / COUNT(DISTINCT w.match_id) >= 2
ORDER BY economy_rate ASC""", notes="Economy is runs / overs summed (weighted), not an average of per-match economies."),
 dict(id=19, level="Advanced", title="Most consistent batters",
      question="Avg runs and standard deviation per player since 2022 (innings of 10+ balls). Lower SD = more consistent.",
      concepts="Custom aggregate STDEV, filtering before aggregation",
      sql="""SELECT p.full_name,
       ROUND(AVG(b.runs), 2) AS avg_runs,
       ROUND(STDEV(b.runs), 2) AS std_dev,
       COUNT(*) AS innings
FROM batting_performances b
JOIN matches m ON m.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
WHERE m.match_date >= '2022-01-01' AND b.balls_faced >= 10
GROUP BY p.player_id, p.full_name
HAVING COUNT(*) >= 10
ORDER BY std_dev ASC""", notes="STDEV is a population-SD aggregate registered in utils/db_connection.py (SQLite has none built in). Minimum 10 innings added so SD is meaningful."),
 dict(id=20, level="Advanced", title="Format workload and averages",
      question="Matches and batting average per format for players with >= 20 total matches.",
      concepts="Pivot with CASE, HAVING on SUM",
      sql="""SELECT p.full_name,
       SUM(CASE WHEN c.match_format = 'Test' THEN c.matches END) AS test_matches,
       SUM(CASE WHEN c.match_format = 'ODI'  THEN c.matches END) AS odi_matches,
       SUM(CASE WHEN c.match_format = 'T20I' THEN c.matches END) AS t20_matches,
       MAX(CASE WHEN c.match_format = 'Test' THEN c.batting_avg END) AS test_avg,
       MAX(CASE WHEN c.match_format = 'ODI'  THEN c.batting_avg END) AS odi_avg,
       MAX(CASE WHEN c.match_format = 'T20I' THEN c.batting_avg END) AS t20_avg
FROM player_career_stats c
JOIN players p ON p.player_id = c.player_id
GROUP BY p.player_id, p.full_name
HAVING SUM(c.matches) >= 20
ORDER BY SUM(c.matches) DESC""", notes=""),
 dict(id=21, level="Advanced", title="Weighted performance ranking",
      question="Combine batting, bowling and fielding into one score and rank the top performers per format.",
      concepts="CTE, ROW_NUMBER() OVER (PARTITION BY ...), weighted formula",
      sql="""WITH scored AS (
    SELECT p.full_name, c.match_format,
           c.runs * 0.01 + COALESCE(c.batting_avg, 0) * 0.5 + COALESCE(c.strike_rate, 0) * 0.3 AS batting_pts,
           c.wickets * 2 + (50 - COALESCE(c.bowling_avg, 50)) * 0.5 + (6 - COALESCE(c.economy, 6)) * 2 AS bowling_pts,
           c.catches * 3 + c.stumpings * 5 AS fielding_pts
    FROM player_career_stats c JOIN players p ON p.player_id = c.player_id
), ranked AS (
    SELECT *, batting_pts + bowling_pts + fielding_pts AS total_pts,
           ROW_NUMBER() OVER (PARTITION BY match_format
                              ORDER BY batting_pts + bowling_pts + fielding_pts DESC) AS rank_in_format
    FROM scored
)
SELECT match_format, rank_in_format AS rank, full_name,
       ROUND(batting_pts, 1) AS batting_pts, ROUND(bowling_pts, 1) AS bowling_pts,
       ROUND(fielding_pts, 1) AS fielding_pts, ROUND(total_pts, 1) AS total_pts
FROM ranked
WHERE rank_in_format <= 10
ORDER BY match_format, rank_in_format""",
      notes="Missing bowling average/economy are treated as the neutral values 50 and 6 so non-bowlers get 0 from those terms."),
 dict(id=22, level="Advanced", title="Head-to-head analysis",
      question="Team pairs with >= 5 matches in the last 3 years: wins, average margins, bat-first vs bowl-first, win %.",
      concepts="CTEs, MIN/MAX pair normalisation, conditional aggregation",
      sql="""WITH h AS (
    SELECT MIN(team1_id, team2_id) AS a, MAX(team1_id, team2_id) AS b, winner_id,
           victory_type, victory_margin,
           CASE WHEN toss_decision = 'bat' THEN toss_winner_id
                ELSE CASE WHEN toss_winner_id = team1_id THEN team2_id ELSE team1_id END END AS bat_first_team
    FROM matches
    WHERE status = 'Complete' AND winner_id IS NOT NULL AND match_date >= date('now', '-3 years')
)
SELECT ta.team_name AS team_a, tb.team_name AS team_b, COUNT(*) AS matches,
       SUM(h.winner_id = h.a) AS a_wins, SUM(h.winner_id = h.b) AS b_wins,
       ROUND(AVG(CASE WHEN h.winner_id = h.a AND h.victory_type = 'runs'    THEN h.victory_margin END), 1) AS a_avg_run_margin,
       ROUND(AVG(CASE WHEN h.winner_id = h.a AND h.victory_type = 'wickets' THEN h.victory_margin END), 1) AS a_avg_wkt_margin,
       ROUND(AVG(CASE WHEN h.winner_id = h.b AND h.victory_type = 'runs'    THEN h.victory_margin END), 1) AS b_avg_run_margin,
       ROUND(AVG(CASE WHEN h.winner_id = h.b AND h.victory_type = 'wickets' THEN h.victory_margin END), 1) AS b_avg_wkt_margin,
       SUM(h.winner_id = h.a AND h.bat_first_team = h.a) AS a_wins_bat_first,
       SUM(h.winner_id = h.a AND h.bat_first_team = h.b) AS a_wins_bowl_first,
       SUM(h.winner_id = h.b AND h.bat_first_team = h.b) AS b_wins_bat_first,
       SUM(h.winner_id = h.b AND h.bat_first_team = h.a) AS b_wins_bowl_first,
       ROUND(100.0 * SUM(h.winner_id = h.a) / COUNT(*), 1) AS a_win_pct,
       ROUND(100.0 * SUM(h.winner_id = h.b) / COUNT(*), 1) AS b_win_pct
FROM h JOIN teams ta ON ta.team_id = h.a JOIN teams tb ON tb.team_id = h.b
GROUP BY h.a, h.b
HAVING COUNT(*) >= 5
ORDER BY matches DESC""",
      notes="Run margins and wicket margins are different units, so they're averaged separately.",
      extra=("Bat-first vs bowl-first wins by venue (same pairs)", """WITH h AS (
    SELECT MIN(team1_id, team2_id) AS a, MAX(team1_id, team2_id) AS b, winner_id, venue_id,
           CASE WHEN toss_decision = 'bat' THEN toss_winner_id
                ELSE CASE WHEN toss_winner_id = team1_id THEN team2_id ELSE team1_id END END AS bat_first_team
    FROM matches
    WHERE status = 'Complete' AND winner_id IS NOT NULL AND match_date >= date('now', '-3 years')
), pairs AS (SELECT a, b FROM h GROUP BY a, b HAVING COUNT(*) >= 5)
SELECT ta.team_name AS team_a, tb.team_name AS team_b, v.venue_name,
       COUNT(*) AS matches,
       SUM(h.winner_id = h.bat_first_team) AS won_batting_first,
       SUM(h.winner_id <> h.bat_first_team) AS won_bowling_first
FROM h JOIN pairs ON pairs.a = h.a AND pairs.b = h.b
JOIN teams ta ON ta.team_id = h.a JOIN teams tb ON tb.team_id = h.b
JOIN venues v ON v.venue_id = h.venue_id
GROUP BY h.a, h.b, v.venue_id
ORDER BY team_a, team_b, matches DESC""")),
 dict(id=23, level="Advanced", title="Player form and momentum",
      question="Last 10 innings per player: avg of last 5 vs 10, strike-rate trend, 50+ scores, consistency, form label.",
      concepts="ROW_NUMBER window, CTEs, CASE classification",
      sql="""WITH recent AS (
    SELECT b.player_id, b.runs, b.strike_rate,
           ROW_NUMBER() OVER (PARTITION BY b.player_id
                              ORDER BY m.match_date DESC, m.match_id DESC, b.innings_no DESC) AS rn
    FROM batting_performances b JOIN matches m ON m.match_id = b.match_id
), agg AS (
    SELECT player_id,
           COUNT(*) AS innings,
           AVG(CASE WHEN rn <= 5 THEN runs END)        AS avg_last5,
           AVG(runs)                                   AS avg_last10,
           AVG(CASE WHEN rn <= 5 THEN strike_rate END) AS sr_last5,
           AVG(strike_rate)                            AS sr_last10,
           SUM(runs >= 50)                             AS fifties,
           STDEV(runs)                                 AS sd
    FROM recent WHERE rn <= 10 GROUP BY player_id HAVING COUNT(*) = 10
)
SELECT p.full_name, ROUND(avg_last5, 1) AS avg_last5, ROUND(avg_last10, 1) AS avg_last10,
       ROUND(sr_last5 - sr_last10, 1) AS sr_trend, fifties AS scores_50_plus,
       ROUND(avg_last10 / NULLIF(sd, 0), 2) AS consistency_score,
       CASE WHEN avg_last5 >= 40 AND fifties >= 3 THEN 'Excellent Form'
            WHEN avg_last5 >= 28 THEN 'Good Form'
            WHEN avg_last5 >= 18 THEN 'Average Form'
            ELSE 'Poor Form' END AS form
FROM agg JOIN players p ON p.player_id = agg.player_id
ORDER BY avg_last5 DESC""",
      notes="Thresholds are our own choice (brief gives labels only): Excellent = last-5 avg >= 40 and >= 3 fifties in 10; Good >= 28; Average >= 18. Consistency = avg / SD (higher = steadier). Positive sr_trend = scoring faster lately."),
 dict(id=24, level="Advanced", title="Best batting pairs",
      question="Pairs batting adjacently in >= 5 partnerships: avg runs, # over 50, highest, success rate.",
      concepts="Self-join, pair normalisation with MIN/MAX, HAVING",
      sql="""WITH pairs AS (
    SELECT MIN(b1.player_id, b2.player_id) AS pa, MAX(b1.player_id, b2.player_id) AS pb,
           b1.runs + b2.runs AS combined
    FROM batting_performances b1
    JOIN batting_performances b2
      ON b2.match_id = b1.match_id AND b2.innings_no = b1.innings_no
     AND b2.batting_position = b1.batting_position + 1
)
SELECT p1.full_name AS player_1, p2.full_name AS player_2,
       COUNT(*) AS partnerships,
       ROUND(AVG(combined), 1) AS avg_runs,
       SUM(combined > 50) AS over_50,
       MAX(combined) AS highest,
       ROUND(100.0 * SUM(combined > 50) / COUNT(*), 1) AS success_rate_pct
FROM pairs
JOIN players p1 ON p1.player_id = pairs.pa
JOIN players p2 ON p2.player_id = pairs.pb
GROUP BY pa, pb
HAVING COUNT(*) >= 5
ORDER BY success_rate_pct DESC, avg_runs DESC
LIMIT 50""", notes="'Good partnership' = more than 50 combined runs."),
 dict(id=25, level="Advanced", title="Career trajectory by quarter",
      question="Quarterly avg runs and strike rate vs previous quarter; classify Ascending / Declining / Stable.",
      concepts="LAG, ROW_NUMBER, CTE chain, trend classification",
      sql="""WITH q AS (
    SELECT b.player_id,
           strftime('%Y', m.match_date) || '-Q' || ((CAST(strftime('%m', m.match_date) AS INTEGER) + 2) / 3) AS quarter,
           AVG(b.runs) AS avg_runs, AVG(b.strike_rate) AS avg_sr, COUNT(DISTINCT m.match_id) AS matches
    FROM batting_performances b JOIN matches m ON m.match_id = b.match_id
    GROUP BY b.player_id, quarter
    HAVING COUNT(DISTINCT m.match_id) >= 3
), s AS (
    SELECT *, LAG(avg_runs) OVER (PARTITION BY player_id ORDER BY quarter) AS prev_runs,
           ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY quarter)      AS rn_asc,
           ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY quarter DESC) AS rn_desc,
           COUNT(*)     OVER (PARTITION BY player_id)                       AS n_quarters
    FROM q
), t AS (
    SELECT player_id, MAX(n_quarters) AS quarters,
           AVG(CASE WHEN rn_asc  <= 3 THEN avg_runs END) AS early_avg,
           AVG(CASE WHEN rn_desc <= 3 THEN avg_runs END) AS recent_avg,
           SUM(avg_runs > prev_runs) AS improving_qtrs,
           SUM(avg_runs < prev_runs) AS declining_qtrs
    FROM s GROUP BY player_id HAVING MAX(n_quarters) >= 6
)
SELECT p.full_name, quarters, ROUND(early_avg, 1) AS early_avg_runs, ROUND(recent_avg, 1) AS recent_avg_runs,
       ROUND(100.0 * (recent_avg - early_avg) / NULLIF(early_avg, 0), 1) AS change_pct,
       improving_qtrs, declining_qtrs,
       CASE WHEN recent_avg >= early_avg * 1.10 THEN 'Career Ascending'
            WHEN recent_avg <= early_avg * 0.90 THEN 'Career Declining'
            ELSE 'Career Stable' END AS career_phase
FROM t JOIN players p ON p.player_id = t.player_id
ORDER BY change_pct DESC""",
      notes="Phase compares the average of the player's last 3 qualifying quarters with their first 3: +/-10% is the stable band. Quarters need >= 3 matches; players need >= 6 such quarters."),
]


def get_query(qid: int) -> dict[str, Any]:
    """Return the query definition for question number ``qid``."""
    for q in QUERIES:
        if q["id"] == qid:
            return q
    raise KeyError(f"No such query: {qid}")


def run_query_by_id(qid: int, db_path=None) -> pd.DataFrame:
    """Execute one of the 25 questions and return its result."""
    return db.run_query(get_query(qid)["sql"], db_path=db_path)
