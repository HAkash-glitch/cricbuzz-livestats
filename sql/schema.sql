-- Cricbuzz LiveStats schema (SQLite dialect; portable to MySQL/PostgreSQL
-- by swapping AUTOINCREMENT -> AUTO_INCREMENT / SERIAL).
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS teams (
    team_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    cb_team_id  INTEGER UNIQUE,          -- Cricbuzz id (NULL for hand-made rows)
    team_name   TEXT NOT NULL UNIQUE,
    country     TEXT NOT NULL,
    short_name  TEXT
);

CREATE TABLE IF NOT EXISTS venues (
    venue_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    cb_venue_id INTEGER UNIQUE,
    venue_name  TEXT NOT NULL,
    city        TEXT NOT NULL,
    country     TEXT NOT NULL,
    capacity    INTEGER CHECK (capacity IS NULL OR capacity > 0),
    UNIQUE (venue_name, city)
);

CREATE TABLE IF NOT EXISTS players (
    player_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    cb_player_id   INTEGER UNIQUE,
    full_name      TEXT NOT NULL,
    team_id        INTEGER NOT NULL REFERENCES teams(team_id) ON DELETE RESTRICT,
    country        TEXT NOT NULL,
    playing_role   TEXT NOT NULL
                   CHECK (playing_role IN ('Batsman','Bowler','All-rounder','Wicket-keeper')),
    batting_style  TEXT,
    bowling_style  TEXT,
    date_of_birth  TEXT,
    UNIQUE (full_name, team_id)
);

CREATE TABLE IF NOT EXISTS series (
    series_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    series_name    TEXT NOT NULL,
    host_country   TEXT NOT NULL,
    match_type     TEXT NOT NULL CHECK (match_type IN ('Test','ODI','T20I')),
    start_date     TEXT NOT NULL,
    total_matches  INTEGER CHECK (total_matches IS NULL OR total_matches > 0)
);

CREATE TABLE IF NOT EXISTS matches (
    match_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    cb_match_id      INTEGER UNIQUE,
    series_id        INTEGER REFERENCES series(series_id) ON DELETE SET NULL,
    description      TEXT NOT NULL,
    match_format     TEXT NOT NULL CHECK (match_format IN ('Test','ODI','T20I')),
    team1_id         INTEGER NOT NULL REFERENCES teams(team_id),
    team2_id         INTEGER NOT NULL REFERENCES teams(team_id),
    venue_id         INTEGER NOT NULL REFERENCES venues(venue_id),
    match_date       TEXT NOT NULL,
    toss_winner_id   INTEGER REFERENCES teams(team_id),
    toss_decision    TEXT CHECK (toss_decision IN ('bat','bowl')),
    winner_id        INTEGER REFERENCES teams(team_id),
    victory_margin   INTEGER CHECK (victory_margin IS NULL OR victory_margin >= 0),
    victory_type     TEXT CHECK (victory_type IN ('runs','wickets')),
    status           TEXT NOT NULL DEFAULT 'Complete'
                     CHECK (status IN ('Complete','Live','Upcoming','No Result')),
    CHECK (team1_id <> team2_id)
);

CREATE TABLE IF NOT EXISTS batting_performances (
    perf_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id         INTEGER NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    player_id        INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    innings_no       INTEGER NOT NULL CHECK (innings_no BETWEEN 1 AND 4),
    batting_position INTEGER NOT NULL CHECK (batting_position BETWEEN 1 AND 11),
    runs             INTEGER NOT NULL CHECK (runs >= 0),
    balls_faced      INTEGER NOT NULL CHECK (balls_faced >= 0),
    fours            INTEGER NOT NULL DEFAULT 0,
    sixes            INTEGER NOT NULL DEFAULT 0,
    strike_rate      REAL,
    is_out           INTEGER NOT NULL DEFAULT 1 CHECK (is_out IN (0,1)),
    UNIQUE (match_id, player_id, innings_no)
);

CREATE TABLE IF NOT EXISTS bowling_performances (
    perf_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id       INTEGER NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    player_id      INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    innings_no     INTEGER NOT NULL CHECK (innings_no BETWEEN 1 AND 4),
    overs          REAL NOT NULL CHECK (overs >= 0),  -- true decimal overs (7.5 = 7 ov 3 balls)
    maidens        INTEGER NOT NULL DEFAULT 0,
    runs_conceded  INTEGER NOT NULL CHECK (runs_conceded >= 0),
    wickets        INTEGER NOT NULL CHECK (wickets BETWEEN 0 AND 10),
    economy        REAL,
    UNIQUE (match_id, player_id, innings_no)
);

CREATE TABLE IF NOT EXISTS fielding_performances (
    match_id    INTEGER NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    player_id   INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    catches     INTEGER NOT NULL DEFAULT 0,
    stumpings   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (match_id, player_id)
);

-- Career aggregates per player per format (what the stats API returns).
CREATE TABLE IF NOT EXISTS player_career_stats (
    player_id      INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    match_format   TEXT NOT NULL CHECK (match_format IN ('Test','ODI','T20I')),
    matches        INTEGER NOT NULL DEFAULT 0,
    innings        INTEGER NOT NULL DEFAULT 0,
    runs           INTEGER NOT NULL DEFAULT 0,
    highest_score  INTEGER NOT NULL DEFAULT 0,
    batting_avg    REAL,
    strike_rate    REAL,
    centuries      INTEGER NOT NULL DEFAULT 0,
    fifties        INTEGER NOT NULL DEFAULT 0,
    wickets        INTEGER NOT NULL DEFAULT 0,
    bowling_avg    REAL,
    economy        REAL,
    catches        INTEGER NOT NULL DEFAULT 0,
    stumpings      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (player_id, match_format)
);

-- Indexes on the columns the 25 analytics queries filter / join on.
CREATE INDEX IF NOT EXISTS idx_players_team      ON players(team_id);
CREATE INDEX IF NOT EXISTS idx_players_role      ON players(playing_role);
CREATE INDEX IF NOT EXISTS idx_matches_date      ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_matches_venue     ON matches(venue_id);
CREATE INDEX IF NOT EXISTS idx_matches_winner    ON matches(winner_id);
CREATE INDEX IF NOT EXISTS idx_matches_teams     ON matches(team1_id, team2_id);
CREATE INDEX IF NOT EXISTS idx_bat_player        ON batting_performances(player_id);
CREATE INDEX IF NOT EXISTS idx_bat_match         ON batting_performances(match_id, innings_no, batting_position);
CREATE INDEX IF NOT EXISTS idx_bowl_player       ON bowling_performances(player_id);
CREATE INDEX IF NOT EXISTS idx_bowl_match        ON bowling_performances(match_id);
CREATE INDEX IF NOT EXISTS idx_series_start      ON series(start_date);
CREATE INDEX IF NOT EXISTS idx_career_format     ON player_career_stats(match_format, runs DESC);

-- Views: reusable joins so the SQL page and queries stay readable.
CREATE VIEW IF NOT EXISTS v_match_details AS
SELECT m.match_id, m.description, m.match_format, m.match_date, m.status,
       t1.team_name AS team1, t2.team_name AS team2,
       t1.country   AS team1_country, t2.country AS team2_country,
       v.venue_name, v.city, v.country AS venue_country,
       w.team_name  AS winner, m.victory_margin, m.victory_type,
       m.toss_winner_id, m.toss_decision, m.team1_id, m.team2_id, m.winner_id
FROM matches m
JOIN teams  t1 ON t1.team_id = m.team1_id
JOIN teams  t2 ON t2.team_id = m.team2_id
JOIN venues v  ON v.venue_id = m.venue_id
LEFT JOIN teams w ON w.team_id = m.winner_id;

CREATE VIEW IF NOT EXISTS v_player_profile AS
SELECT p.player_id, p.full_name, p.country, t.team_name, p.playing_role,
       p.batting_style, p.bowling_style
FROM players p JOIN teams t ON t.team_id = p.team_id;
