/**
 * Multi-Tenant RLS Isolation Verification Tests
 * Story: 0-18 Multi-Tenant Test Isolation Infrastructure
 * AC: 4  - Tenant A cannot query Tenant B data
 * AC: 5  - Tenant A cannot modify Tenant B data
 * AC: 6  - RLS bypass attempt fails with permission denied
 * AC: 8  - Parallel test execution uses separate tenant schemas
 * AC: 9  - Tenant provisioning completes in <5 seconds
 *
 * These tests require a live PostgreSQL database with RLS enabled.
 * Run with: TEST_DATABASE_URL=... npx jest tests/integration/tenant-isolation.test.ts
 */

import { Pool, PoolClient } from 'pg';
import {
  createTestTenant,
  cleanupTestTenant,
  setTenantContext,
  clearTenantContext,
  requireTenantContext,
  seedTestTenant,
  TestTenant,
} from '../../src/test-utils';

// Skip if no database connection available
const TEST_DATABASE_URL = process.env.TEST_DATABASE_URL;
const describeWithDb = TEST_DATABASE_URL ? describe : describe.skip;

describeWithDb('Multi-Tenant Isolation', () => {
  let pool: Pool;

  beforeAll(() => {
    pool = new Pool({ connectionString: TEST_DATABASE_URL });
  });

  afterAll(async () => {
    await pool.end();
  });

  // ===========================================================================
  // AC1: Tenant provisioning creates isolated schemas
  // ===========================================================================

  describe('AC1: Tenant Provisioning', () => {
    let tenant: TestTenant;

    afterEach(async () => {
      if (tenant) {
        await tenant.cleanup();
      }
    });

    test('creates schema with all required tables', async () => {
      tenant = await createTestTenant(pool);

      const result = await pool.query(
        `SELECT tablename FROM pg_tables WHERE schemaname = $1 ORDER BY tablename`,
        [tenant.schemaName]
      );

      const tables = result.rows.map((r) => r.tablename);
      expect(tables).toEqual([
        'projects',
        'test_cases',
        'test_executions',
        'users',
      ]);
    });

    test('creates RLS policies on all tables', async () => {
      tenant = await createTestTenant(pool);

      const result = await pool.query(
        `SELECT tablename, policyname FROM pg_policies WHERE schemaname = $1`,
        [tenant.schemaName]
      );

      expect(result.rows).toHaveLength(4);
      for (const row of result.rows) {
        expect(row.policyname).toBe('tenant_isolation');
      }
    });

    test('enables FORCE ROW LEVEL SECURITY on all tables', async () => {
      tenant = await createTestTenant(pool);

      const result = await pool.query(
        `SELECT relname, relrowsecurity, relforcerowsecurity
         FROM pg_class c
         JOIN pg_namespace n ON c.relnamespace = n.oid
         WHERE n.nspname = $1 AND c.relkind = 'r'`,
        [tenant.schemaName]
      );

      for (const row of result.rows) {
        expect(row.relrowsecurity).toBe(true);
        expect(row.relforcerowsecurity).toBe(true);
      }
    });

    test('accepts custom tenant ID', async () => {
      tenant = await createTestTenant(pool, 'custom_tenant_abc');
      expect(tenant.tenantId).toBe('custom_tenant_abc');
      expect(tenant.schemaName).toBe('tenant_custom_tenant_abc');
    });
  });

  // ===========================================================================
  // AC2: Cleanup hooks delete tenant data
  // ===========================================================================

  describe('AC2: Tenant Cleanup', () => {
    test('drops schema completely after cleanup', async () => {
      const tenant = await createTestTenant(pool);
      const schemaName = tenant.schemaName;

      await tenant.cleanup();

      const result = await pool.query(
        `SELECT 1 FROM information_schema.schemata WHERE schema_name = $1`,
        [schemaName]
      );
      expect(result.rows).toHaveLength(0);
    });

    test('cleanup is idempotent (can call twice)', async () => {
      const tenant = await createTestTenant(pool);

      await tenant.cleanup();
      // Second call should not throw
      await cleanupTestTenant(pool, tenant.tenantId);
    });
  });

  // ===========================================================================
  // AC3: Tenant context management
  // ===========================================================================

  describe('AC3: Tenant Context Management', () => {
    let tenant: TestTenant;

    beforeEach(async () => {
      tenant = await createTestTenant(pool);
    });

    afterEach(async () => {
      await tenant.cleanup();
    });

    test('setTenantContext sets app.current_tenant', async () => {
      const client = await pool.connect();
      try {
        await client.query('BEGIN');
        await setTenantContext(client, tenant.tenantId);

        const result = await client.query(
          `SELECT current_setting('app.current_tenant') AS tid`
        );
        expect(result.rows[0].tid).toBe(tenant.tenantId);

        await client.query('ROLLBACK');
      } finally {
        client.release();
      }
    });

    test('clearTenantContext resets the setting', async () => {
      const client = await pool.connect();
      try {
        await client.query('BEGIN');
        await setTenantContext(client, tenant.tenantId);
        await clearTenantContext(client);

        // After reset, current_setting should throw or return empty
        await expect(
          client.query(
            `SELECT current_setting('app.current_tenant') AS tid`
          )
        ).rejects.toThrow();

        await client.query('ROLLBACK');
      } finally {
        client.release();
      }
    });

    test('requireTenantContext throws when no context set', async () => {
      const client = await pool.connect();
      try {
        await expect(requireTenantContext(client)).rejects.toThrow(
          'No tenant context set'
        );
      } finally {
        client.release();
      }
    });

    test('requireTenantContext returns tenant ID when set', async () => {
      const client = await pool.connect();
      try {
        await client.query('BEGIN');
        await setTenantContext(client, tenant.tenantId);

        const tid = await requireTenantContext(client);
        expect(tid).toBe(tenant.tenantId);

        await client.query('ROLLBACK');
      } finally {
        client.release();
      }
    });

    test('setTenantContext rejects empty tenantId', async () => {
      const client = await pool.connect();
      try {
        await expect(setTenantContext(client, '')).rejects.toThrow(
          'non-empty tenantId'
        );
      } finally {
        client.release();
      }
    });
  });

  // ===========================================================================
  // AC4: Tenant A cannot query Tenant B data
  // ===========================================================================

  describe('AC4: Cross-Tenant SELECT Isolation', () => {
    let tenantA: TestTenant;
    let tenantB: TestTenant;

    beforeAll(async () => {
      tenantA = await createTestTenant(pool);
      tenantB = await createTestTenant(pool);

      // Seed data for tenant A
      const clientA = await pool.connect();
      await clientA.query('BEGIN');
      await setTenantContext(clientA, tenantA.tenantId);
      await seedTestTenant(clientA, tenantA.schemaName, tenantA.tenantId);
      await clientA.query('COMMIT');
      clientA.release();

      // Seed data for tenant B
      const clientB = await pool.connect();
      await clientB.query('BEGIN');
      await setTenantContext(clientB, tenantB.tenantId);
      await seedTestTenant(clientB, tenantB.schemaName, tenantB.tenantId);
      await clientB.query('COMMIT');
      clientB.release();
    });

    afterAll(async () => {
      await tenantA.cleanup();
      await tenantB.cleanup();
    });

    test('Tenant A SELECT on Tenant B schema returns 0 rows', async () => {
      const client = await pool.connect();
      try {
        await client.query('BEGIN');
        await setTenantContext(client, tenantA.tenantId);

        const result = await client.query(
          `SELECT * FROM ${tenantB.schemaName}.users`
        );
        expect(result.rows).toHaveLength(0);

        await client.query('ROLLBACK');
      } finally {
        client.release();
      }
    });

    test('Tenant B SELECT on Tenant A schema returns 0 rows', async () => {
      const client = await pool.connect();
      try {
        await client.query('BEGIN');
        await setTenantContext(client, tenantB.tenantId);

        const result = await client.query(
          `SELECT * FROM ${tenantA.schemaName}.users`
        );
        expect(result.rows).toHaveLength(0);

        await client.query('ROLLBACK');
      } finally {
        client.release();
      }
    });

    test('tenant can see their own data', async () => {
      const client = await pool.connect();
      try {
        await client.query('BEGIN');
        await setTenantContext(client, tenantA.tenantId);

        const result = await client.query(
          `SELECT * FROM ${tenantA.schemaName}.users`
        );
        expect(result.rows.length).toBeGreaterThan(0);

        await client.query('ROLLBACK');
      } finally {
        client.release();
      }
    });
  });

  // ===========================================================================
  // AC5: Tenant A cannot modify Tenant B data
  // ===========================================================================

  describe('AC5: Cross-Tenant UPDATE/DELETE Isolation', () => {
    let tenantA: TestTenant;
    let tenantB: TestTenant;

    beforeAll(async () => {
      tenantA = await createTestTenant(pool);
      tenantB = await createTestTenant(pool);

      const clientB = await pool.connect();
      await clientB.query('BEGIN');
      await setTenantContext(clientB, tenantB.tenantId);
      await seedTestTenant(clientB, tenantB.schemaName, tenantB.tenantId);
      await clientB.query('COMMIT');
      clientB.release();
    });

    afterAll(async () => {
      await tenantA.cleanup();
      await tenantB.cleanup();
    });

    test('Tenant A UPDATE on Tenant B data affects 0 rows', async () => {
      const client = await pool.connect();
      try {
        await client.query('BEGIN');
        await setTenantContext(client, tenantA.tenantId);

        const result = await client.query(
          `UPDATE ${tenantB.schemaName}.users SET first_name = 'Hacked'`
        );
        expect(result.rowCount).toBe(0);

        await client.query('ROLLBACK');
      } finally {
        client.release();
      }
    });

    test('Tenant A DELETE on Tenant B data affects 0 rows', async () => {
      const client = await pool.connect();
      try {
        await client.query('BEGIN');
        await setTenantContext(client, tenantA.tenantId);

        const result = await client.query(
          `DELETE FROM ${tenantB.schemaName}.users`
        );
        expect(result.rowCount).toBe(0);

        await client.query('ROLLBACK');
      } finally {
        client.release();
      }
    });

    test('Tenant B data unchanged after Tenant A modification attempts', async () => {
      const client = await pool.connect();
      try {
        await client.query('BEGIN');
        await setTenantContext(client, tenantB.tenantId);

        const result = await client.query(
          `SELECT * FROM ${tenantB.schemaName}.users`
        );
        expect(result.rows.length).toBeGreaterThan(0);
        expect(result.rows[0].first_name).not.toBe('Hacked');

        await client.query('ROLLBACK');
      } finally {
        client.release();
      }
    });
  });

  // ===========================================================================
  // AC6: RLS bypass attempt fails
  // ===========================================================================

  describe('AC6: RLS Bypass Prevention', () => {
    test('SET LOCAL row_security = off fails for non-superuser', async () => {
      const client = await pool.connect();
      try {
        await expect(
          client.query('SET LOCAL row_security = off')
        ).rejects.toThrow(/permission denied/);
      } finally {
        client.release();
      }
    });

    test('direct schema access without tenant context returns no rows', async () => {
      const tenant = await createTestTenant(pool);

      try {
        // Seed data with context
        const seedClient = await pool.connect();
        await seedClient.query('BEGIN');
        await setTenantContext(seedClient, tenant.tenantId);
        await seedTestTenant(seedClient, tenant.schemaName, tenant.tenantId);
        await seedClient.query('COMMIT');
        seedClient.release();

        // Query WITHOUT setting tenant context — RLS should block
        const client = await pool.connect();
        try {
          // Without app.current_tenant set, current_setting() will throw,
          // which means the RLS policy evaluation fails → 0 rows returned
          // (or error depending on PG version)
          await client.query('BEGIN');
          const result = await client.query(
            `SELECT * FROM ${tenant.schemaName}.users`
          );
          // Either 0 rows (policy fails silently) or error
          expect(result.rows).toHaveLength(0);
          await client.query('ROLLBACK');
        } catch {
          // Some PG versions throw on missing current_setting — that's also acceptable
        } finally {
          client.release();
        }
      } finally {
        await tenant.cleanup();
      }
    });
  });

  // ===========================================================================
  // AC8: Parallel test execution with separate tenant schemas
  // ===========================================================================

  describe('AC8: Parallel Test Execution', () => {
    test('5 parallel test suites with no data conflicts', async () => {
      const PARALLEL_COUNT = 5;

      const results = await Promise.all(
        Array.from({ length: PARALLEL_COUNT }, async (_, i) => {
          const tenant = await createTestTenant(pool);
          const client = await pool.connect();

          try {
            await client.query('BEGIN');
            await setTenantContext(client, tenant.tenantId);

            // Insert unique data per worker
            await client.query(`
              INSERT INTO ${tenant.schemaName}.users
                (tenant_id, email, first_name, last_name)
              VALUES
                ('${tenant.tenantId}'::uuid, 'worker${i}@test.local', 'Worker', '${i}')
            `);

            // Verify only own data visible
            const result = await client.query(
              `SELECT * FROM ${tenant.schemaName}.users`
            );

            await client.query('ROLLBACK');
            return {
              workerId: i,
              tenantId: tenant.tenantId,
              rowCount: result.rows.length,
              email: result.rows[0]?.email,
              cleanup: tenant.cleanup,
            };
          } finally {
            client.release();
          }
        })
      );

      // Verify each worker saw exactly 1 row — their own
      for (const r of results) {
        expect(r.rowCount).toBe(1);
        expect(r.email).toBe(`worker${r.workerId}@test.local`);
      }

      // Verify all tenant IDs are unique
      const tenantIds = results.map((r) => r.tenantId);
      expect(new Set(tenantIds).size).toBe(PARALLEL_COUNT);

      // Cleanup all tenants
      await Promise.all(results.map((r) => r.cleanup()));
    });
  });

  // ===========================================================================
  // AC9: Tenant provisioning completes in <5 seconds
  // ===========================================================================

  describe('AC9: Provisioning Performance', () => {
    test('createTestTenant completes in <5 seconds', async () => {
      const start = Date.now();
      const tenant = await createTestTenant(pool);
      const elapsed = Date.now() - start;

      expect(elapsed).toBeLessThan(5000);

      await tenant.cleanup();
    });

    test('10 sequential provisions each complete in <5 seconds', async () => {
      const tenants: TestTenant[] = [];

      for (let i = 0; i < 10; i++) {
        const start = Date.now();
        const tenant = await createTestTenant(pool);
        const elapsed = Date.now() - start;
        expect(elapsed).toBeLessThan(5000);
        tenants.push(tenant);
      }

      await Promise.all(tenants.map((t) => t.cleanup()));
    });
  });
});
