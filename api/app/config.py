"""Settings read from the environment. Locally they come from the repo-root .env."""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str  # Direct connection, for Alembic. Migrations shouldn't run through the pooler.
    database_url_pooled: str  # Pooled connection, for the app.

    @field_validator("database_url", "database_url_pooled")
    @classmethod
    def use_psycopg_driver(cls, url: str) -> str:
        # Neon hands out postgresql:// URLs, and SQLAlchemy needs to be told to use psycopg 3.
        # sslmode and channel_binding stay in the URL: psycopg understands them, asyncpg doesn't.
        return url.replace("postgresql://", "postgresql+psycopg://", 1)


settings = Settings()
