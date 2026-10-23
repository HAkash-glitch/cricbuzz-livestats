"""Smoke-test every Streamlit page with Streamlit's AppTest (no browser needed)."""
import pytest
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]

PAGES = [str(ROOT / "pages" / n) for n in ("live_matches.py", "top_stats.py",
                                           "sql_queries.py", "crud_operations.py")]


@pytest.fixture(autouse=True)
def _no_api_key(monkeypatch):
    import config
    monkeypatch.setattr(config, "RAPIDAPI_KEY", "")


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page):
    at = AppTest.from_file(page, default_timeout=30).run()
    assert not at.exception, [e.value for e in at.exception]


def test_sql_page_every_question_renders():
    at = AppTest.from_file(str(ROOT / "pages" / "sql_queries.py"), default_timeout=30).run()
    sel = at.selectbox[0]
    for opt in sel.options:
        at = sel.select(opt).run()
        assert not at.exception, (opt, [e.value for e in at.exception])
        assert not at.error, (opt, [e.value for e in at.error])
        sel = at.selectbox[0]


def test_custom_sql_rejects_delete():
    at = AppTest.from_file(str(ROOT / "pages" / "sql_queries.py"), default_timeout=30).run()
    at.text_area[0].set_value("DELETE FROM players").run()
    at.button[0].click().run()
    assert any("Only SELECT" in e.value for e in at.error)


def test_app_entry_renders_home_with_navigation():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Cricbuzz LiveStats" in at.title[0].value
