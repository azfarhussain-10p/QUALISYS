"""
Backend Test Configuration
Story: 1-1-user-account-creation (Task 6), 1-2-organization-creation-setup (Task 7)
Provides async test client, test DB session, and Redis mock.

Patterns:
  - Each test runs in a transaction that is ROLLED BACK after the test (fast isolation)
  - Redis calls are mocked with fakeredis (no live Redis required for unit/integration)
  - Database connection requires TEST_DATABASE_URL env var; tests skip if not set
"""

import os
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from faker import Faker
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db import get_db
from src.main import app
from src.models.base import Base
from src.models.user import User
from src.models.tenant import Tenant, TenantUser

fake = Faker()


# ---------------------------------------------------------------------------
# Test database engine (uses in-memory SQLite for unit tests or TEST_DATABASE_URL)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    test_db_url = os.getenv(
        "TEST_DATABASE_URL",
        "sqlite+aiosqlite:///:memory:",
    )
    # Use asyncpg for PostgreSQL, aiosqlite for SQLite
    engine = create_async_engine(test_db_url, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Per-test database session that rolls back after each test.
    Provides isolation without recreating the schema.
    """
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with TestSessionLocal() as session:
        async with session.begin():
            yield session
            await session.rollback()


# ---------------------------------------------------------------------------
# FastAPI async test client with DB override
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    AsyncClient targeting the FastAPI app.
    Overrides the `get_db` dependency to use the test session.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with patch("src.cache.get_redis_client", return_value=_mock_redis()):
        with patch("src.middleware.rate_limit.get_redis_client", return_value=_mock_redis()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                yield ac

    app.dependency_overrides.clear()


def _mock_redis():
    """
    Returns a mock Redis client suitable for unit/integration tests.

    Design:
      - Never trips rate limits (incr always returns 1, ttl=60)
      - Never trips lockout (exists always returns 0)
      - Token operations (get, set, getdel) return safe defaults
      - Pipeline is sync-chainable with async execute()
    """
    mock = MagicMock()

    # Pipeline: all commands are chainable MagicMocks; execute is async
    pipeline = MagicMock()
    pipeline.set = MagicMock(return_value=pipeline)
    pipeline.get = MagicMock(return_value=pipeline)
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.ttl = MagicMock(return_value=pipeline)
    pipeline.sadd = MagicMock(return_value=pipeline)
    pipeline.srem = MagicMock(return_value=pipeline)
    pipeline.delete = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[1, 60, True, True])  # never rate-limited
    mock.pipeline.return_value = pipeline

    # Direct async methods
    mock.get = AsyncMock(return_value=None)           # no sessions stored
    mock.set = AsyncMock(return_value=True)
    mock.getdel = AsyncMock(return_value=None)        # token not found (no rotation in unit tests)
    mock.delete = AsyncMock(return_value=1)
    mock.exists = AsyncMock(return_value=0)           # no lockout
    mock.incr = AsyncMock(return_value=1)             # first attempt → no rate limit
    mock.expire = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.smembers = AsyncMock(return_value=set())     # no active sessions
    mock.sadd = AsyncMock(return_value=1)
    mock.srem = AsyncMock(return_value=1)
    mock.scan = AsyncMock(return_value=(0, []))       # no session keys to delete
    mock.ping = AsyncMock(return_value=True)
    return mock


# ---------------------------------------------------------------------------
# Test data factories
# ---------------------------------------------------------------------------

def make_user_payload(**overrides) -> dict:
    """Generate valid RegisterRequest payload."""
    return {
        "email": overrides.get("email", fake.email()),
        "password": overrides.get("password", "SecurePass123!"),
        "full_name": overrides.get("full_name", fake.name()),
    }


@pytest_asyncio.fixture
async def existing_user(db_session: AsyncSession) -> User:
    """Creates and persists a test user (email/password, unverified)."""
    from src.services.auth.auth_service import hash_password

    user = User(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        full_name="Test User",
        password_hash=hash_password("SecurePass123!"),
        email_verified=False,
        auth_provider="email",
    )
    db_session.add(user)
    await db_session.flush()
    return user


# ---------------------------------------------------------------------------
# Story 1.2 fixtures — tenant + RBAC helpers
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession, existing_user: User) -> Tenant:
    """
    Creates and persists a test Tenant with existing_user as owner.
    MUST be created in Story 1.2 (public.tenants did not exist in Story 1.1).
    """
    slug = f"test-org-{uuid.uuid4().hex[:6]}"
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Test Organization",
        slug=slug,
        data_retention_days=365,
        plan="free",
        settings={},
        created_by=existing_user.id,
    )
    db_session.add(tenant)
    await db_session.flush()

    membership = TenantUser(
        tenant_id=tenant.id,
        user_id=existing_user.id,
        role="owner",
    )
    db_session.add(membership)

    existing_user.default_tenant_id = tenant.id
    db_session.add(existing_user)
    await db_session.flush()

    return tenant


@pytest.fixture
def auth_headers(existing_user: User) -> dict:
    """
    Returns Authorization: Bearer headers for existing_user.
    Uses create_access_token so the JWT matches the RBAC middleware exactly.
    """
    from src.services.auth.auth_service import create_access_token

    token = create_access_token(existing_user.id, existing_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def client_with_auth(
    db_session: AsyncSession,
    existing_user: User,
    auth_headers: dict,
) -> AsyncGenerator[AsyncClient, None]:
    """
    AsyncClient pre-configured with auth headers for existing_user.
    Used by Story 1.2+ tests that need authenticated requests.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with patch("src.cache.get_redis_client", return_value=_mock_redis()):
        with patch("src.middleware.rate_limit.get_redis_client", return_value=_mock_redis()):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers=auth_headers,
            ) as ac:
                yield ac

    app.dependency_overrides.clear()
