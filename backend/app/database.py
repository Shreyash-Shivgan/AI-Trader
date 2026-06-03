from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _sync_database_url(database_url: str) -> str:
    """Return a sync SQLAlchemy URL for the database engine.

    The app uses a synchronous ORM/session pattern. If the configured URL uses
    an async driver such as asyncpg, translate it to the sync psycopg2 driver
    so startup and metadata creation can run without greenlet/await issues.
    """
    url = make_url(database_url)
    if url.drivername.endswith("+asyncpg"):
        url = url.set(drivername=url.drivername.replace("+asyncpg", "+psycopg2"))
    elif url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg2")
    return str(url)


engine = create_engine(
    _sync_database_url(settings.database_url),
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


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


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import entities  # noqa: F401

    Base.metadata.create_all(bind=engine)
