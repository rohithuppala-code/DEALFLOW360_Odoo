"""Health endpoints.

``/health`` proves the whole vertical slice the frontend depends on: FastAPI is
serving, SQLAlchemy can open a session, and PostgreSQL answers a real query.
"""

import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.session import Base, engine
from app.dependencies.db import get_db
from app.schemas.health import DatabaseHealth, HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


def _check_database(db: Session) -> DatabaseHealth:
    """Run a real query against PostgreSQL and report what came back."""
    expected = len(Base.metadata.tables)
    try:
        db.execute(text("SELECT 1"))
        server_version = db.execute(text("SHOW server_version")).scalar_one()
        database_name = db.execute(text("SELECT current_database()")).scalar_one()
        present = len(inspect(db.get_bind()).get_table_names(schema="public"))
        return DatabaseHealth(
            connected=True,
            dialect=engine.dialect.name,
            server_version=str(server_version),
            database=str(database_name),
            tables_present=present,
            tables_expected=expected,
        )
    except SQLAlchemyError as exc:
        # The message is logged in full but only a short form is returned, so a
        # failed health probe never leaks the connection string.
        logger.warning("PostgreSQL health check failed: %s", exc)
        return DatabaseHealth(
            connected=False,
            dialect=engine.dialect.name,
            tables_expected=expected,
            error=type(exc).__name__,
        )


@router.get("/health", response_model=HealthResponse)
def health(response: Response, db: Session = Depends(get_db)) -> HealthResponse:
    """Report API and PostgreSQL health.

    Returns 503 when the database is unreachable so that uptime checks and the
    frontend status banner both see the failure instead of a green 200.
    """
    database = _check_database(db)
    if not database.connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if database.connected else "degraded",
        app=settings.APP_NAME,
        environment=settings.APP_ENV,
        database=database,
    )
