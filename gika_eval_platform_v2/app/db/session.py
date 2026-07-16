
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

# check_same_thread=False so Streamlit / uvicorn threads can share the engine.
_connect_args = {"check_same_thread": False} if _settings.db_url.startswith("sqlite") else {}

engine: Engine = create_engine(
    _settings.db_url,
    echo=False,
    future=True,
    connect_args=_connect_args,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
    if _settings.db_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Session:
    return SessionLocal()


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
