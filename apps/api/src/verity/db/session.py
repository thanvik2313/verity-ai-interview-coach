"""Async database engine and session management.

Provides:
  - `get_engine()` / `get_sessionmaker()`: process-wide, lazily created and
    cached, so the engine's connection pool is built once per process.
  - `get_db()`: a FastAPI dependency yielding a request-scoped
    `AsyncSession`, committing on success and rolling back on error.
  - `dispose_engine()`: called from the app's shutdown lifespan so pooled
    connections are closed cleanly instead of left open at process exit.

No ORM models are imported here — this module only manages connectivity.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from verity.core.config import Settings, get_settings


def _build_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        str(settings.database_url),
        # Conservative defaults for a stateless API instance; tuned per
        # environment (Railway process sizing) rather than hardcoded higher.
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        # SQL echo is opt-in via engine.echo toggling elsewhere in tests; it
        # must never be enabled by default in case it logs bound parameters
        # containing candidate data (Architecture.md §9).
        echo=False,
    )


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, creating it on first use."""
    return _build_engine(get_settings())


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide async session factory, creating it on first use."""
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped `AsyncSession`.

    Commits if the request handler completes without raising; rolls back
    and re-raises otherwise. The session is always closed, returning its
    connection to the pool.
    """
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def dispose_engine() -> None:
    """Dispose the process-wide engine's connection pool.

    Call from the application's shutdown lifespan.
    """
    engine = get_engine()
    await engine.dispose()
    # Clear the cached engine/sessionmaker so a subsequent get_engine() call
    # (e.g. in tests that patch settings between runs) builds a fresh engine
    # rather than reusing a disposed one.
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
