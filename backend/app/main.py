"""DealFlow360 FastAPI application entry point."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.db import base as _model_registry  # noqa: F401  (registers every ORM model)
from app.routers import health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description=(
        "Sales operations platform API: discount governance, automated approval "
        "routing, multi-warehouse fulfilment, hybrid billing and customer negotiation."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health lives at both / and /api so container probes and the React client can
# each use the path they expect.
app.include_router(health.router)
app.include_router(health.router, prefix=settings.API_PREFIX)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "name": settings.APP_NAME,
        "version": "0.1.0",
        "docs": "/docs",
        "health": f"{settings.API_PREFIX}/health",
    }
