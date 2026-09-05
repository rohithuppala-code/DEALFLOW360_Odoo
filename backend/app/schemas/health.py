"""Response schemas for the health endpoints."""

from typing import Optional

from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    connected: bool = Field(description="True when SELECT 1 succeeded against PostgreSQL")
    dialect: str = Field(description="SQLAlchemy dialect in use; must be postgresql")
    server_version: Optional[str] = Field(default=None, description="PostgreSQL server version")
    database: Optional[str] = Field(default=None, description="Connected database name")
    tables_present: int = Field(default=0, description="Tables found in the public schema")
    tables_expected: int = Field(default=0, description="Tables declared by the ORM models")
    error: Optional[str] = Field(default=None, description="Connection error, if any")


class HealthResponse(BaseModel):
    status: str = Field(description="ok when the API and PostgreSQL are both healthy")
    app: str
    environment: str
    api: str = "up"
    database: DatabaseHealth
