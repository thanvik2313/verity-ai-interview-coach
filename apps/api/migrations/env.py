"""Alembic migration environment.

Runs async, using the same SQLAlchemy async engine machinery as the
application (TechStack.md §3), and reads the database URL from
verity.core.config.get_settings() — never a hardcoded connection string or
a value duplicated from .env into alembic.ini (Database.md §8).
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from verity.core.config import get_settings
from verity.db.base import Base

# Importing the identity module's models registers User on Base.metadata
# so `alembic revision --autogenerate` (for future migrations; this
# revision itself is hand-written) can see it.
from verity.modules.identity.domain.models import User  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Resolve the migration target URL from application settings.

    Never reads alembic.ini's sqlalchemy.url (left blank there
    deliberately) — a single VERITY_DATABASE_URL environment variable
    drives both the app and its migrations.
    """
    return str(get_settings().database_url)


def run_migrations_offline() -> None:
    """Emit SQL without a live database connection (`alembic upgrade --sql`)."""
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations_sync(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against a live database using the async engine."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_run_migrations_sync)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())