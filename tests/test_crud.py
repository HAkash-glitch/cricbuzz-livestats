import pytest

from services import crud_service as svc
from utils import db_connection as db


def _p(**kw):
    base = dict(full_name="Test Player", team_id=1, playing_role="Batsman")
    base.update(kw)
    return svc.PlayerInput(**base)


def test_create_read_update_delete_player(fresh_db):
    pid = svc.create_player(_p(), fresh_db)
    assert svc.get_player(pid, fresh_db)["full_name"] == "Test Player"
    assert svc.update_player(pid, _p(full_name="Renamed Player", playing_role="Bowler"), fresh_db)
    assert svc.get_player(pid, fresh_db)["playing_role"] == "Bowler"
    assert svc.delete_player(pid, fresh_db)
    assert svc.get_player(pid, fresh_db) is None
    assert svc.delete_player(pid, fresh_db) is False


@pytest.mark.parametrize("kw", [dict(full_name=" "), dict(playing_role="Umpire"),
                                dict(date_of_birth="31/12/1990"), dict(date_of_birth="1800-01-01")])
def test_player_validation(fresh_db, kw):
    with pytest.raises(svc.ValidationError):
        svc.create_player(_p(**kw), fresh_db)


def test_duplicate_player_rejected(fresh_db):
    svc.create_player(_p(), fresh_db)
    with pytest.raises(svc.ValidationError):
        svc.create_player(_p(), fresh_db)


def test_unknown_team_rejected(fresh_db):
    with pytest.raises(svc.ValidationError):
        svc.create_player(_p(team_id=9999), fresh_db)


def test_delete_player_cascades_stats(fresh_db):
    pid = int(db.run_query("SELECT player_id FROM player_career_stats LIMIT 1", db_path=fresh_db).player_id[0])
    svc.delete_player(pid, fresh_db)
    assert db.run_query("SELECT COUNT(*) n FROM player_career_stats WHERE player_id=?", [pid], fresh_db).n[0] == 0


def test_career_stat_upsert_and_validation(fresh_db):
    pid = svc.create_player(_p(), fresh_db)
    svc.upsert_career_stat(svc.CareerStatInput(pid, "ODI", 10, 10, 400, 120, 40.0, 90.0, 1, 2), fresh_db)
    svc.upsert_career_stat(svc.CareerStatInput(pid, "ODI", 11, 11, 450, 120, 41.0, 91.0, 1, 3), fresh_db)
    df = svc.get_career_stats(pid, fresh_db)
    assert len(df) == 1 and df.runs[0] == 450
    with pytest.raises(svc.ValidationError):
        svc.upsert_career_stat(svc.CareerStatInput(pid, "ODI", 5, 5, 100, 200), fresh_db)  # HS > runs
    with pytest.raises(svc.ValidationError):
        svc.upsert_career_stat(svc.CareerStatInput(pid, "ODI", 5, 9, 100, 50), fresh_db)   # innings > matches
    with pytest.raises(svc.ValidationError):
        svc.upsert_career_stat(svc.CareerStatInput(9999, "ODI", 1, 1, 1, 1), fresh_db)


def test_match_create_result_delete(fresh_db):
    mid = svc.create_match("Test fixture", "T20I", 1, 2, 1, "2030-01-01", db_path=fresh_db)
    assert svc.record_result(mid, 1, 20, "runs", fresh_db)
    row = db.run_query("SELECT status, winner_id FROM matches WHERE match_id=?", [mid], fresh_db).iloc[0]
    assert row.status == "Complete" and row.winner_id == 1
    with pytest.raises(svc.ValidationError):
        svc.record_result(mid, 3, 5, "runs", fresh_db)      # winner not in match
    with pytest.raises(svc.ValidationError):
        svc.create_match("x", "T20I", 1, 1, 1, "2030-01-01", db_path=fresh_db)  # same team
    assert svc.delete_match(mid, fresh_db) and not svc.delete_match(mid, fresh_db)
