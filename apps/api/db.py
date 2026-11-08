"""Database engine and session helpers (SQLite via SQLModel)."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

import settings

_engines: dict[str, object] = {}


def get_engine(db_path: Path | str | None = None):
    path = str(db_path or settings.DB_PATH)
    if path not in _engines:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        _engines[path] = engine
    return _engines[path]


def init_db(db_path: Path | str | None = None):
    import models  # noqa: F401  registers tables

    engine = get_engine(db_path)
    SQLModel.metadata.create_all(engine)
    _add_missing_columns(engine)
    return engine


def _add_missing_columns(engine) -> None:
    """Small forward-only migration: add columns that newer models define to older databases."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                ddl_type = col.type.compile(engine.dialect)
                default = col.default.arg if col.default is not None and not callable(col.default.arg) else None
                clause = f" DEFAULT {default!r}" if isinstance(default, (str, int, float)) else ""
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl_type}{clause}'))


def dispose(db_path: Path | str | None = None) -> None:
    path = str(db_path or settings.DB_PATH)
    engine = _engines.pop(path, None)
    if engine is not None:
        engine.dispose()


@contextmanager
def session_scope(db_path: Path | str | None = None) -> Iterator[Session]:
    with Session(get_engine(db_path)) as session:
        yield session


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with Session(get_engine()) as session:
        yield session
