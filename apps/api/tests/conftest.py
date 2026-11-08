from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

import db
from seed.generate import build

END_DATE = date(2026, 10, 10)


@pytest.fixture(scope="session")
def seeded_db(tmp_path_factory) -> Path:
    """The full 90-day seeded restaurant, built once per test run."""
    out = tmp_path_factory.mktemp("seed")
    return build(out, seed=42, end_date=END_DATE)


@pytest.fixture
def work_db(seeded_db, tmp_path) -> Path:
    """A private copy of the seeded database that a test may change."""
    path = tmp_path / "tadka.sqlite"
    shutil.copy(seeded_db, path)
    db.init_db(path)
    yield path
    db.dispose(path)
