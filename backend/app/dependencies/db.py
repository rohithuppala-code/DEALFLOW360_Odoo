"""FastAPI database dependency."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped session and always close it.

    The session is rolled back on any unhandled exception so a failed request
    can never leave a half-applied transaction behind.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
