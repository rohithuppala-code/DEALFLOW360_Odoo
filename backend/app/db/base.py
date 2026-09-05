"""Metadata aggregation point.

Importing this module guarantees that every ORM model is registered on
``Base.metadata``. Alembic autogenerate and the health check both rely on it.
"""

from app.db.session import Base  # noqa: F401
from app.models import *  # noqa: F401,F403
