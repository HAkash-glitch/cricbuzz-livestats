
import pytest

from utils import db_connection as db


def test_schema_tables_views_indexes(db_path):
    names = db.run_query("SELECT name, type FROM sqlite_master", db_path=db_path)
    assert {"teams", "players", "matches", "batting_performances", "player_career_stats"} <= set(names.name)
    assert {"v_match_details", "v_player_profile"} <= set(names[names.type == "view"].name)
    assert (names.type == "index").sum() >= 10


def test_foreign_keys_enforced(fresh_db):
    with pytest.raises(db.DatabaseError):
        db.execute("INSERT INTO players(full_name,team_id,country,playing_role) VALUES ('X Y',9999,'Z','Bowler')",
                   db_path=fresh_db)


def test_check_constraint_role(fresh_db):
    with pytest.raises(db.DatabaseError):
        db.execute("INSERT INTO players(full_name,team_id,country,playing_role) VALUES ('X Y',1,'Z','Goalkeeper')",
                   db_path=fresh_db)


def test_transaction_rolls_back(fresh_db):
    before = db.table_count("teams", fresh_db)
    with pytest.raises(db.DatabaseError):
        with db.transaction(fresh_db) as conn:
            conn.execute("INSERT INTO teams(team_name,country) VALUES ('Temp','Temp')")
            conn.execute("INSERT INTO teams(team_name,country) VALUES ('Temp','Temp')")  # duplicate
    assert db.table_count("teams", fresh_db) == before


def test_seed_data_integrity(db_path):
    # every decided match has a winner that played in it; margins present
    bad = db.run_query("SELECT COUNT(*) n FROM matches WHERE winner_id IS NOT NULL AND winner_id NOT IN (team1_id, team2_id)",
                       db_path=db_path)
    assert bad.n[0] == 0
    orphan = db.run_query("SELECT COUNT(*) n FROM batting_performances b "
                          "LEFT JOIN players p USING(player_id) WHERE p.player_id IS NULL",
                          db_path=db_path)
    assert orphan.n[0] == 0
    assert db.table_count("matches", db_path) > 300


def test_readonly_runner_blocks_writes(db_path):
    for bad in ["DELETE FROM players", "SELECT 1; DROP TABLE players", "UPDATE players SET full_name='x'",
                "WITH x AS (SELECT 1) DELETE FROM players", ""]:
        with pytest.raises(db.DatabaseError):
            db.run_readonly(bad, db_path)
    assert db.run_readonly("select count(*) n from players", db_path).n[0] > 0
    assert db.table_count("players", db_path) > 0  # nothing was deleted


def test_table_count_rejects_unknown_table(db_path):
    with pytest.raises(ValueError):
        db.table_count("players; DROP TABLE players", db_path)
