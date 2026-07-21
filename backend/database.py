"""Database engine, sessions, and bootstrap helpers."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

import config


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


def create_database_engine(url: str = config.DATABASE_URL) -> Engine:
    """Create a SQLAlchemy engine with safe SQLite defaults."""
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    database_engine = create_engine(url, connect_args=connect_args, future=True)

    if url.startswith("sqlite"):

        @event.listens_for(database_engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return database_engine


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_database(bind: Engine = engine) -> None:
    """Create all current tables.

    This is the bootstrap migration for the local application. SQLAlchemy's
    metadata operation is idempotent, so it is safe to run at every startup.
    """
    # Import models here so every table has been registered with Base.
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind)


@contextmanager
def session_scope(factory: sessionmaker = SessionLocal) -> Iterator[Session]:
    """Provide a transactional session for services and background workers."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
