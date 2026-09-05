"""SQLAlchemy engine, session factory and declarative base.

PostgreSQL is the single source of truth for the whole platform; the engine is
built from DATABASE_URL only, so pointing the app at a different PostgreSQL
server never requires a code change.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config.settings import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO,
    pool_pre_ping=True,   # transparently recycles connections dropped by the server
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""
