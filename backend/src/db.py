"""
QUALISYS API — Async Database Engine & Session Factory
Story: 1-1-user-account-creation
AC: AC4 — parameterized queries via SQLAlchemy ORM
AC: AC7 — all DB operations via ORM (no raw SQL string concatenation)
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# Engine (single instance shared across requests)
# ---------------------------------------------------------------------------

engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yields a database session, rolling back on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Health check helper (for /ready endpoint — Story 0-21 pattern)
# ---------------------------------------------------------------------------

async def check_database() -> dict:
    """Returns {"status": "ok"} or raises an exception."""
    async with AsyncSessionLocal() as session:
        await session.execute(__import__("sqlalchemy").text("SELECT 1"))
    return {"status": "ok"}
