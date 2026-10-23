import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import seed_data  # noqa: E402


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    """A freshly seeded temp DB shared by read-only tests."""
    path = tmp_path_factory.mktemp("db") / "test.db"
    seed_data.build(path)
    return path


@pytest.fixture()
def fresh_db(tmp_path):
    """A private seeded DB for tests that write."""
    path = tmp_path / "w.db"
    seed_data.build(path)
    return path
