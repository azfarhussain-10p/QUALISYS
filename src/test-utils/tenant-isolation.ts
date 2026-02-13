/**
 * Multi-Tenant Test Isolation Utilities
 * Story: 0-18 Multi-Tenant Test Isolation Infrastructure
 * AC: 1  - createTestTenant() creates isolated tenant schemas
 * AC: 2  - cleanupTestTenant() deletes tenant data after tests
 * AC: 3  - setTenantContext() enforces tenant scope
 * AC: 9  - Provisioning completes in <5 seconds
 * AC: 10 - Documented with usage examples
 *
 * Usage:
 *   import { createTestTenant, cleanupTestTenant } from '../src/test-utils';
 *
 *   const tenant = await createTestTenant(pool);
 *   // ... run tests with tenant.tenantId ...
 *   await tenant.cleanup();
 */

import { Pool, PoolClient } from 'pg';
import { randomUUID } from 'crypto';

// =============================================================================
// Types
// =============================================================================

export interface TestTenant {
  tenantId: string;
  schemaName: string;
  cleanup: () => Promise<void>;
}

// =============================================================================
// Identifier Validation (SQL injection prevention)
// =============================================================================

const SAFE_IDENTIFIER = /^[a-z0-9_]+$/;

function assertSafeIdentifier(name: string): void {
  if (!SAFE_IDENTIFIER.test(name)) {
    throw new Error(
      `Unsafe SQL identifier: "${name}". Only lowercase alphanumeric and underscores allowed.`
    );
  }
}

// =============================================================================
// Tenant Provisioning (AC1, AC9)
// =============================================================================

/**
 * Creates an isolated test tenant with its own schema, tables, and RLS policies.
 *
 * Each call creates a fresh schema with the full table set (users, projects,
 * test_cases, test_executions) and RLS policies that enforce tenant isolation
 * via `app.current_tenant` session variable.
 *
 * @param pool - PostgreSQL connection pool
 * @param tenantId - Optional fixed tenant ID (defaults to UUID)
 * @returns TestTenant with tenantId, schemaName, and cleanup function
 *
 * @example
 *   const tenant = await createTestTenant(pool);
 *   console.log(tenant.schemaName); // "tenant_test_a1b2c3..."
 *   await tenant.cleanup(); // drops schema
 */
export async function createTestTenant(
  pool: Pool,
  tenantId?: string
): Promise<TestTenant> {
  const id = tenantId ?? `test_${randomUUID().replace(/-/g, '')}`;
  const schemaName = `tenant_${id}`;
  assertSafeIdentifier(schemaName);

  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // --- Schema creation ---
    await client.query(`CREATE SCHEMA ${schemaName}`);

    // --- Tables (matches seed.ts schema from Story 0-15) ---
    await client.query(`
      CREATE TABLE ${schemaName}.users (
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

      CREATE TABLE ${schemaName}.projects (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID NOT NULL,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        organization_id UUID,
        settings JSONB DEFAULT '{}',
        is_active BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
      );

      CREATE TABLE ${schemaName}.test_cases (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID NOT NULL,
        project_id UUID NOT NULL,
        title VARCHAR(500) NOT NULL,
        description TEXT,
        priority VARCHAR(50) NOT NULL DEFAULT 'medium',
        status VARCHAR(50) NOT NULL DEFAULT 'active',
        steps JSONB DEFAULT '[]',
        tags TEXT[] DEFAULT '{}',
        estimated_duration INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
      );

      CREATE TABLE ${schemaName}.test_executions (
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
        screenshots TEXT[] DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
      )
    `);

    // --- Enable RLS + FORCE (AC6: even table owner cannot bypass) ---
    const tables = ['users', 'projects', 'test_cases', 'test_executions'];
    for (const table of tables) {
      await client.query(
        `ALTER TABLE ${schemaName}.${table} ENABLE ROW LEVEL SECURITY`
      );
      await client.query(
        `ALTER TABLE ${schemaName}.${table} FORCE ROW LEVEL SECURITY`
      );

      // RLS policy: only rows matching app.current_tenant are visible
      await client.query(`
        CREATE POLICY tenant_isolation ON ${schemaName}.${table}
          USING (tenant_id = current_setting('app.current_tenant')::uuid)
          WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)
      `);
    }

    await client.query('COMMIT');

    return {
      tenantId: id,
      schemaName,
      cleanup: () => cleanupTestTenant(pool, id),
    };
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
}

// =============================================================================
// Tenant Cleanup (AC2)
// =============================================================================

/**
 * Drops a test tenant schema and all its data.
 *
 * Uses CASCADE to remove all dependent objects (tables, policies, indexes).
 * Verifies the schema no longer exists after dropping.
 *
 * @param pool - PostgreSQL connection pool
 * @param tenantId - The tenant ID to clean up
 *
 * @example
 *   await cleanupTestTenant(pool, 'test_a1b2c3...');
 */
export async function cleanupTestTenant(
  pool: Pool,
  tenantId: string
): Promise<void> {
  const schemaName = `tenant_${tenantId}`;
  assertSafeIdentifier(schemaName);

  await pool.query(`DROP SCHEMA IF EXISTS ${schemaName} CASCADE`);

  // Verify cleanup (AC2: confirm schema removed)
  const result = await pool.query(
    `SELECT 1 FROM information_schema.schemata WHERE schema_name = $1`,
    [schemaName]
  );

  if (result.rows.length > 0) {
    throw new Error(`Cleanup failed: schema ${schemaName} still exists`);
  }
}

// =============================================================================
// Tenant Context Management (AC3)
// =============================================================================

/**
 * Sets the current tenant context on a database connection.
 *
 * Uses SET LOCAL so the setting is scoped to the current transaction.
 * RLS policies use `current_setting('app.current_tenant')` to filter rows.
 *
 * @param client - Active database connection (must be within a transaction for SET LOCAL)
 * @param tenantId - The tenant UUID to set as current context
 */
export async function setTenantContext(
  client: PoolClient,
  tenantId: string
): Promise<void> {
  if (!tenantId) {
    throw new Error('Tenant context requires a non-empty tenantId');
  }
  await client.query(`SET LOCAL app.current_tenant = '${tenantId}'`);
}

/**
 * Clears the current tenant context on a database connection.
 *
 * @param client - Active database connection
 */
export async function clearTenantContext(client: PoolClient): Promise<void> {
  await client.query('RESET app.current_tenant');
}

/**
 * Validates that a tenant context is currently set on the connection.
 * Throws if no context is set (AC3: reject operations without context).
 *
 * @param client - Active database connection
 * @returns The current tenant ID
 */
export async function requireTenantContext(
  client: PoolClient
): Promise<string> {
  try {
    const result = await client.query(
      `SELECT current_setting('app.current_tenant') AS tenant_id`
    );
    const tenantId = result.rows[0]?.tenant_id;
    if (!tenantId) {
      throw new Error('No tenant context set');
    }
    return tenantId;
  } catch {
    throw new Error(
      'No tenant context set. Call setTenantContext() before database operations.'
    );
  }
}

// =============================================================================
// Seed Helpers (AC1: Task 1.4)
// =============================================================================

/**
 * Inserts minimal seed data into a test tenant schema.
 * Useful for tests that need pre-existing data.
 *
 * @param client - Database connection with tenant context already set
 * @param schemaName - The tenant schema name
 * @param tenantId - The tenant UUID
 */
export async function seedTestTenant(
  client: PoolClient,
  schemaName: string,
  tenantId: string
): Promise<{ userId: string; projectId: string }> {
  assertSafeIdentifier(schemaName);

  const userResult = await client.query(`
    INSERT INTO ${schemaName}.users (tenant_id, email, first_name, last_name, role)
    VALUES ('${tenantId}'::uuid, 'test-user@${schemaName}.local', 'Test', 'User', 'admin')
    RETURNING id
  `);

  const projectResult = await client.query(`
    INSERT INTO ${schemaName}.projects (tenant_id, name, organization_id)
    VALUES ('${tenantId}'::uuid, 'Test Project', NULL)
    RETURNING id
  `);

  return {
    userId: userResult.rows[0].id,
    projectId: projectResult.rows[0].id,
  };
}
