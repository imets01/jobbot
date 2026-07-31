"""Database engine, sessions, and bootstrap helpers."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event, inspect
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
    _apply_sqlite_bootstrap_migrations(bind)


def _apply_sqlite_bootstrap_migrations(bind: Engine) -> None:
    """Add columns introduced after the first local schema release.

    The app predates Alembic and is deliberately local-first. These additive,
    idempotent migrations preserve existing SQLite data while new installations
    receive the complete schema directly from SQLAlchemy metadata.
    """
    if bind.dialect.name != "sqlite":
        return

    additions = {
        "jobs": {
            "dismissed": "BOOLEAN NOT NULL DEFAULT 0",
        },
        "analysis_runs": {
            "hidden": "BOOLEAN NOT NULL DEFAULT 0",
        },
        "search_settings": {
            "greenhouse_boards_json": "TEXT NOT NULL DEFAULT '[]'",
            "lever_sites_json": "TEXT NOT NULL DEFAULT '[]'",
        },
        "candidate_profiles": {
            "structured_json": "TEXT NOT NULL DEFAULT '{}'",
        },
        "analysis_results": {
            "match_score": "INTEGER",
            "qualifies": "BOOLEAN",
            "recommendation_label": "VARCHAR(40)",
            "short_explanation": "TEXT NOT NULL DEFAULT ''",
            "score_breakdown_json": "TEXT NOT NULL DEFAULT '{}'",
            "matched_strengths_json": "TEXT NOT NULL DEFAULT '[]'",
            "weak_areas_json": "TEXT NOT NULL DEFAULT '[]'",
            "potential_concerns_json": "TEXT NOT NULL DEFAULT '[]'",
            "missing_requirements_json": "TEXT NOT NULL DEFAULT '[]'",
            "resume_keywords_json": "TEXT NOT NULL DEFAULT '[]'",
            "application_strategy": "TEXT NOT NULL DEFAULT ''",
            "work_model": "VARCHAR(30)",
            "required_experience_years": "FLOAT",
            "required_languages_json": "TEXT NOT NULL DEFAULT '[]'",
            "critical_gaps_json": "TEXT NOT NULL DEFAULT '[]'",
        },
    }

    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())
    with bind.begin() as connection:
        for table_name, columns in additions.items():
            if table_name not in table_names:
                continue
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, definition in columns.items():
                if column_name not in existing:
                    connection.exec_driver_sql(
                        f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {definition}'
                    )


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
