"""
Pytest Tenant Isolation Fixtures
Story: 0-18 Multi-Tenant Test Isolation Infrastructure
AC: 7  - Test framework configured to run tests in isolated tenant contexts
AC: 3  - Tenant context management enforces tenant scope
AC: 8  - Parallel test execution uses separate tenant schemas (pytest-xdist)

Usage:
    def test_something(test_tenant, tenant_connection):
        # test_tenant = {"tenant_id": "...", "schema_name": "..."}
        # tenant_connection = asyncpg connection with tenant context set

    def test_parallel(test_tenant):
        # Each xdist worker gets a unique tenant schema
"""

import os
import uuid

import pytest
import pytest_asyncio
import asyncpg


# =============================================================================
# Database Pool
# =============================================================================

@pytest_asyncio.fixture(scope="session")
async def db_pool():
    """Session-scoped connection pool for the test database."""
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL not set")

    pool = await asyncpg.create_pool(dsn=dsn, min_size=2, max_size=10)
    yield pool
    await pool.close()


# =============================================================================
# Tenant Provisioning (AC1, AC8)
# =============================================================================

TENANT_TABLES_DDL = """
CREATE TABLE {schema}.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(255) NOT NULL DEFAULT '',
    last_name VARCHAR(255) NOT NULL DEFAULT '',
    role VARCHAR(50) NOT NULL DEFAULT 'member',
    organization_id UUID,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE {schema}.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    organization_id UUID,
    settings JSONB DEFAULT '{{}}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE {schema}.test_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    project_id UUID NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    priority VARCHAR(50) NOT NULL DEFAULT 'medium',
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    steps JSONB DEFAULT '[]'::jsonb,
    tags TEXT[] DEFAULT '{{}}',
    estimated_duration INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE {schema}.test_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    test_case_id UUID NOT NULL,
    status VARCHAR(50) NOT NULL,
    executed_by UUID,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    duration INTEGER DEFAULT 0,
    environment VARCHAR(100),
    browser VARCHAR(100),
    notes TEXT,
    error_message TEXT,
    screenshots TEXT[] DEFAULT '{{}}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

RLS_POLICY_DDL = """
ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {schema}.{table} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {schema}.{table}
    USING (tenant_id = current_setting('app.current_tenant')::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);
"""


@pytest_asyncio.fixture
async def test_tenant(db_pool):
    """
    Creates an isolated test tenant schema per test.

    Each pytest-xdist worker gets a unique UUID-based tenant ID,
    preventing parallel test conflicts (AC8).

    Yields:
        dict with tenant_id and schema_name
    """
    tenant_id = f"test_{uuid.uuid4().hex}"
    schema_name = f"tenant_{tenant_id}"

    async with db_pool.acquire() as conn:
        await conn.execute(f"CREATE SCHEMA {schema_name}")
        await conn.execute(TENANT_TABLES_DDL.format(schema=schema_name))

        for table in ["users", "projects", "test_cases", "test_executions"]:
            await conn.execute(
                RLS_POLICY_DDL.format(schema=schema_name, table=table)
            )

    yield {"tenant_id": tenant_id, "schema_name": schema_name}

    # Cleanup: drop schema and all objects
    async with db_pool.acquire() as conn:
        await conn.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")


# =============================================================================
# Tenant Context (AC3, AC7)
# =============================================================================

@pytest_asyncio.fixture
async def tenant_connection(db_pool, test_tenant):
    """
    Provides a database connection with tenant context set inside a transaction.

    The connection has app.current_tenant set to the test tenant's ID.
    Transaction is rolled back after the test for fast cleanup.

    Yields:
        asyncpg.Connection with tenant context
    """
    conn = await db_pool.acquire()
    tr = conn.transaction()
    await tr.start()

    await conn.execute(
        f"SET LOCAL app.current_tenant = '{test_tenant['tenant_id']}'"
    )

    yield conn

    await tr.rollback()
    await db_pool.release(conn)
