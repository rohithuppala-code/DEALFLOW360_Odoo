"""Application configuration.

Every deployment-specific value is read from the environment (backend/.env) so
that no credential or business constant is baked into the source tree.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application -------------------------------------------------------
    APP_NAME: str = "DealFlow360 API"
    APP_ENV: str = "development"
    API_PREFIX: str = "/api"

    # --- Database ----------------------------------------------------------
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/dealflow360"
    SQL_ECHO: bool = False

    # --- Authentication (used from Step 4 onwards) -------------------------
    JWT_SECRET_KEY: str = "change-me-to-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # --- CORS --------------------------------------------------------------
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Settings are cached so the .env file is parsed exactly once per process."""
    return Settings()


settings = get_settings()
