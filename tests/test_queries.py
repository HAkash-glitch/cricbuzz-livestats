import pytest

from services.queries import QUERIES, get_query, run_query_by_id
from utils import db_connection as db


def test_there_are_25_questions_in_order():
    assert [q["id"] for q in QUERIES] == list(range(1, 26))
    assert [q["level"] for q in QUERIES].count("Beginner") == 8
    assert [q["level"] for q in QUERIES].count("Intermediate") == 8
    assert [q["level"] for q in QUERIES].count("Advanced") == 9


@pytest.mark.parametrize("qid", range(1, 26))
def test_query_runs_and_returns_rows(db_path, qid):
    df = run_query_by_id(qid, db_path)
    assert len(df) > 0, f"Q{qid} returned no rows"


def test_q5_matches_independent_count(db_path):
    got = run_query_by_id(5, db_path).set_index("team_name").total_wins.to_dict()
    raw = db.run_query("SELECT winner_id, COUNT(*) n FROM matches WHERE winner_id IS NOT NULL GROUP BY 1", db_path=db_path)
    teams = db.run_query("SELECT team_id, team_name FROM teams", db_path=db_path).set_index("team_id").team_name
    assert got == {teams[r.winner_id]: r.n for r in raw.itertuples()}


def test_q12_home_plus_away_equals_twice_decided_matches(db_path):
    df = run_query_by_id(12, db_path)
    decided = db.run_query("SELECT COUNT(*) n FROM matches WHERE status='Complete' AND winner_id IS NOT NULL",
                           db_path=db_path).n[0]
    assert (df.home_matches + df.away_matches).sum() == 2 * decided
    assert (df.home_wins + df.away_wins).sum() == decided


def test_q17_all_row_is_consistent(db_path):
    df = run_query_by_id(17, db_path).set_index("toss_decision")
    assert df.loc["ALL", "matches"] == df.loc["bat", "matches"] + df.loc["bowl", "matches"]
    assert 0 <= df.loc["ALL", "win_pct"] <= 100


def test_q3_sorted_and_limited(db_path):
    df = run_query_by_id(3, db_path)
    assert len(df) == 10 and df.total_runs.is_monotonic_decreasing


def test_q25_phase_labels(db_path):
    df = run_query_by_id(25, db_path)
    assert set(df.career_phase) <= {"Career Ascending", "Career Declining", "Career Stable"}
    assert (df.quarters >= 6).all()


def test_q23_form_labels_and_window(db_path):
    df = run_query_by_id(23, db_path)
    assert set(df.form) <= {"Excellent Form", "Good Form", "Average Form", "Poor Form"}


def test_q21_top10_per_format(db_path):
    df = run_query_by_id(21, db_path)
    assert df.groupby("match_format").size().max() == 10


def test_get_query_unknown():
    with pytest.raises(KeyError):
        get_query(99)
