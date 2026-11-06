"""Runs migrations over the direct connection, because they shouldn't go through the pooler."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import Base

if context.config.config_file_name:
    # Keep the app's and pytest's loggers working when migrations run inside a test run.
    fileConfig(context.config.config_file_name, disable_existing_loggers=False)

# Pass the URL straight to the engine: Alembic's ini handling treats % in a URL as interpolation.
engine = create_engine(settings.database_url, poolclass=NullPool)

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
