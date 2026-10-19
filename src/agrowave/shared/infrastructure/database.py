"""Database engine and connectivity check utilities."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from agrowave.settings import Settings


@lru_cache(maxsize=1)
def get_engine(database_url: str | None = None) -> Engine:
    """Creates and caches a SQLModel engine.

    Args:
        database_url: Optional override database connection URL. If omitted,
            uses Settings().database_url.

    Returns:
        The initialized SQLModel Engine instance.
    """
    url = database_url or Settings().database_url
    return create_engine(url, echo=False, pool_pre_ping=True)


def get_session(engine: Engine | None = None) -> Generator[Session, None, None]:
    """Yields a database session.

    Args:
        engine: Optional Engine to bind to. Defaults to cached get_engine().

    Yields:
        An active SQLModel Session.
    """
    eng = engine or get_engine()
    with Session(eng) as session:
        yield session


def ping_database(engine: Engine | None = None) -> bool:
    """Checks whether the database is responsive.

    Executes a lightweight SELECT 1 query to verify connectivity.

    Args:
        engine: Optional Engine instance to test. Defaults to get_engine().

    Returns:
        True if the database responds, False otherwise.
    """
    try:
        eng = engine or get_engine()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
