"""Settings read from the environment. Locally they come from the repo-root .env."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # env_ignore_empty: a blank line such as DEMO_MODE= means "not set", not an invalid value.
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", extra="ignore", env_ignore_empty=True
    )

    database_url: str  # Direct connection, for Alembic. Migrations shouldn't run through the pooler.
    database_url_pooled: str  # Pooled connection, for the app.
    session_secret: str = Field(min_length=32)  # Signs office sessions. 32 bytes suits HS256.
    driver_link_secret: str = Field(min_length=32)  # Keys the stored hash of each driver token.
    web_origin: str  # The web app's URL.
    demo_mode: bool = False

    @field_validator("database_url", "database_url_pooled")
    @classmethod
    def use_psycopg_driver(cls, url: str) -> str:
        # Neon hands out postgresql:// URLs, and SQLAlchemy needs to be told to use psycopg 3.
        # sslmode and channel_binding stay in the URL: psycopg understands them, asyncpg doesn't.
        return url.replace("postgresql://", "postgresql+psycopg://", 1)

    @property
    def cookie_secure(self) -> bool:
        # Secure cookies only travel over https, so local http development has to turn it off.
        return not self.web_origin.startswith("http://")


settings = Settings()
