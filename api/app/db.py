"""The app's database engine and the session dependency for routes."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url_pooled,
    connect_args={
        "prepare_threshold": None,  # The Neon pooler must never see prepared statements.
        "connect_timeout": 10,  # A health check should fail, not hang.
    },
    pool_pre_ping=True,  # Neon suspends when idle, which kills pooled connections.
)
# expire_on_commit=False: a route can commit, then read the row for its response without a query.
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
