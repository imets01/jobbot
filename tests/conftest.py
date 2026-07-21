from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

from backend.database import Base, create_database_engine


@pytest.fixture
def session_factory(tmp_path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def session(session_factory):
    with session_factory() as db:
        yield db
        db.rollback()
