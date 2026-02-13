/**
 * Jest Tenant Isolation Fixtures
 * Story: 0-18 Multi-Tenant Test Isolation Infrastructure
 * AC: 7  - Test framework configured to run tests in isolated tenant contexts
 * AC: 3  - Tenant context management enforces scope
 * AC: 8  - Parallel test execution uses separate tenant schemas
 *
 * Provides Jest hooks and a decorator for automatic tenant lifecycle
 * management in integration tests.
 *
 * Usage (describe-level):
 *   import { useTenantIsolation } from '../src/test-utils';
 *
 *   describe('MyService', () => {
 *     const ctx = useTenantIsolation();
 *
 *     test('creates a record', async () => {
 *       const { client, schemaName, tenantId } = ctx.current();
 *       // client already has tenant context set within a transaction
 *     });
 *   });
 *
 * Usage (per-test decorator):
 *   import { withTenantIsolation } from '../src/test-utils';
 *
 *   test('isolated test', withTenantIsolation(async ({ client, tenantId }) => {
 *     // runs inside isolated tenant transaction
 *   }));
 */

import { Pool, PoolClient } from 'pg';
import {
  createTestTenant,
  setTenantContext,
  TestTenant,
} from './tenant-isolation';

// =============================================================================
// Types
// =============================================================================

export interface TenantTestContext {
  pool: Pool;
  client: PoolClient;
  tenant: TestTenant;
  tenantId: string;
  schemaName: string;
}

// =============================================================================
// Describe-Level Fixture (AC7: beforeEach/afterEach hooks)
// =============================================================================

/**
 * Creates Jest lifecycle hooks for tenant isolation.
 *
 * Call inside a `describe()` block. Each test gets:
 * - A fresh tenant schema (unique per test for parallel safety)
 * - A database client with tenant context set inside a transaction
 * - Automatic rollback + schema cleanup in afterEach
 *
 * @param connectionString - Override TEST_DATABASE_URL (defaults to env var)
 * @returns Object with `current()` accessor for the active test context
 *
 * @example
 *   describe('Tenant-scoped tests', () => {
 *     const ctx = useTenantIsolation();
 *
 *     test('example', async () => {
 *       const { client, tenantId, schemaName } = ctx.current();
 *       await client.query(`INSERT INTO ${schemaName}.users ...`);
 *     });
 *   });
 */
export function useTenantIsolation(connectionString?: string) {
  let pool: Pool;
  let testCtx: TenantTestContext | null = null;

  beforeAll(() => {
    const connStr =
      connectionString ?? process.env.TEST_DATABASE_URL;
    if (!connStr) {
      throw new Error('TEST_DATABASE_URL environment variable is required');
    }
    pool = new Pool({ connectionString: connStr });
  });

  beforeEach(async () => {
    // Create isolated tenant schema (AC1)
    const tenant = await createTestTenant(pool);

    // Acquire client and start transaction
    const client = await pool.connect();
    await client.query('BEGIN');

    // Set tenant context for RLS (AC3)
    await setTenantContext(client, tenant.tenantId);

    testCtx = {
      pool,
      client,
      tenant,
      tenantId: tenant.tenantId,
      schemaName: tenant.schemaName,
    };
  });

  afterEach(async () => {
    if (testCtx) {
      // Rollback transaction for fast cleanup (AC2: Task 2.4)
      try {
        await testCtx.client.query('ROLLBACK');
      } catch {
        // Connection may already be released
      }
      testCtx.client.release();

      // Drop tenant schema completely (AC2: Task 2.3)
      await testCtx.tenant.cleanup();
      testCtx = null;
    }
  });

  afterAll(async () => {
    if (pool) {
      await pool.end();
    }
  });

  return {
    /** Returns the current test's tenant context. Throws if called outside a test. */
    current(): TenantTestContext {
      if (!testCtx) {
        throw new Error(
          'No active tenant context. Ensure useTenantIsolation() is called inside describe().'
        );
      }
      return testCtx;
    },
  };
}

// =============================================================================
// Per-Test Decorator (AC3: Task 3.6)
// =============================================================================

/**
 * Wraps a test function with automatic tenant isolation.
 *
 * Creates a tenant, sets context, runs the test, then cleans up.
 * Useful for standalone tests outside of describe blocks.
 *
 * @param fn - Test function receiving TenantTestContext
 * @param connectionString - Override TEST_DATABASE_URL
 *
 * @example
 *   test('isolated', withTenantIsolation(async ({ client, schemaName }) => {
 *     const res = await client.query(`SELECT * FROM ${schemaName}.users`);
 *     expect(res.rows).toHaveLength(0);
 *   }));
 */
export function withTenantIsolation(
  fn: (ctx: TenantTestContext) => Promise<void>,
  connectionString?: string
): () => Promise<void> {
  return async () => {
    const connStr =
      connectionString ?? process.env.TEST_DATABASE_URL;
    if (!connStr) {
      throw new Error('TEST_DATABASE_URL environment variable is required');
    }

    const pool = new Pool({ connectionString: connStr });
    let client: PoolClient | null = null;

    try {
      const tenant = await createTestTenant(pool);
      client = await pool.connect();
      await client.query('BEGIN');
      await setTenantContext(client, tenant.tenantId);

      await fn({
        pool,
        client,
        tenant,
        tenantId: tenant.tenantId,
        schemaName: tenant.schemaName,
      });

      await client.query('ROLLBACK');
      client.release();
      client = null;
      await tenant.cleanup();
    } finally {
      if (client) {
        try {
          await client.query('ROLLBACK');
        } catch {
          // ignore
        }
        client.release();
      }
      await pool.end();
    }
  };
}
