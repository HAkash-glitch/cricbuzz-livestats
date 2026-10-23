import json

import pytest
import requests

import config
from api.cricbuzz_client import (ApiError, CricbuzzClient, parse_match_list, parse_scorecard, parse_top_stats)
from services import sync_service
from utils import db_connection as db


class FakeResp:
    def __init__(self, status=200, payload=None, headers=None, bad_json=False):
        self.status_code, self._p, self.headers, self._bad = status, payload or {}, headers or {}, bad_json

    def json(self):
        if self._bad:
            raise ValueError("bad")
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class FakeSession:
    def __init__(self, seq):
        self.seq, self.calls = list(seq), 0

    def get(self, *a, **k):
        self.calls += 1
        item = self.seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def client(seq, key="k", retries=2):
    return CricbuzzClient(api_key=key, session=FakeSession(seq), max_retries=retries, backoff=0)


def test_no_key_raises():
    with pytest.raises(ApiError, match="RAPIDAPI_KEY"):
        client([], key="").get("x")


def test_success():
    assert client([FakeResp(payload={"a": 1})]).get("x") == {"a": 1}


def test_retries_then_succeeds():
    c = client([FakeResp(503), requests.ConnectionError("boom"), FakeResp(payload={"ok": 1})])
    assert c.get("x") == {"ok": 1} and c.session.calls == 3


def test_gives_up_after_retries():
    c = client([requests.Timeout()] * 3)
    with pytest.raises(ApiError, match="Network failure"):
        c.get("x")
    assert c.session.calls == 3


def test_auth_error_not_retried():
    c = client([FakeResp(403), FakeResp(200)])
    with pytest.raises(ApiError, match="rejected"):
        c.get("x")
    assert c.session.calls == 1


def test_bad_json():
    with pytest.raises(ApiError, match="Invalid JSON"):
        client([FakeResp(bad_json=True)]).get("x")


def test_rate_limit_message():
    with pytest.raises(ApiError, match="Rate limit"):
        client([FakeResp(429)], retries=0).get("x")


def test_parse_demo_fixture():
    ms = parse_match_list(json.loads(config.SAMPLE_LIVE_FILE.read_text()))
    assert len(ms) == 2 and ms[0]["format"] == "ODI" and ms[1]["format"] == "T20I"
    assert ms[0]["team1_score"] == "211/6 (38.4 ov)"
    assert parse_match_list({}) == []


def test_parse_scorecard_and_topstats():
    sc = parse_scorecard(json.loads((config.BASE_DIR / "data" / "sample_scorecard.json").read_text()))
    assert sc[0]["batting"][0]["Batter"] == "A. Sample" and len(sc[0]["bowling"]) == 2
    h, r = parse_top_stats({"headers": ["Player", "Runs"], "values": [{"values": ["A", "10"]}]})
    assert h == ["Player", "Runs"] and r == [["A", "10"]]


def test_sync_is_idempotent(fresh_db):
    ms = parse_match_list(json.loads(config.SAMPLE_LIVE_FILE.read_text()))
    before = db.table_count("matches", fresh_db)
    assert sync_service.save_matches(ms, fresh_db) == 2
    assert sync_service.save_matches(ms, fresh_db) == 2
    assert db.table_count("matches", fresh_db) == before + 2
    assert sync_service.save_matches([{"match_id": 1}], fresh_db) == 0  # incomplete record skipped
