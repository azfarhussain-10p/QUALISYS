/**
 * Test Database Reset Script
 * Story: 0-14 Test Database Provisioning
 * AC: 4  - Database reset mechanism for clean test runs
 * AC: 9  - Database migrations run successfully on test database
 *
 * Truncates all tables in test tenant schemas while preserving
 * schema structure, RLS policies, and indexes.
 *
 * Usage:
 *   npm run db:reset:test
 *   npx ts-node scripts/db-reset.ts
 *
 * Environment:
 *   TEST_DATABASE_URL - PostgreSQL connection string for test database
 *
 * Performance target: <30 seconds for full reset
 */

import { Pool, PoolClient } from 'pg';

const TEST_SCHEMAS = ['tenant_test_1', 'tenant_test_2', 'tenant_test_3'];

async function resetDatabase(): Promise<void> {
  const connectionString = process.env.TEST_DATABASE_URL;

  if (!connectionString) {
    console.error('ERROR: TEST_DATABASE_URL environment variable is not set');
    process.exit(1);
  }

  // Safety check: refuse to run against production
  if (
    connectionString.includes('qualisys_master') ||
    connectionString.includes('production')
  ) {
    console.error('ERROR: Refusing to reset a production database!');
    console.error('TEST_DATABASE_URL must point to qualisys_test');
    process.exit(1);
  }

  const pool = new Pool({ connectionString });
  let client: PoolClient | null = null;
  const startTime = Date.now();

  try {
    client = await pool.connect();

    console.log('Starting test database reset...');
    console.log(`Schemas: ${TEST_SCHEMAS.join(', ')}`);

    // Disable triggers temporarily for faster truncation
    await client.query(`SET session_replication_role = 'replica'`);

    for (const schema of TEST_SCHEMAS) {
      // Get all tables in this schema
      const result = await client.query(
        `SELECT tablename FROM pg_tables WHERE schemaname = $1`,
        [schema]
      );

      if (result.rows.length === 0) {
        console.log(`  ${schema}: no tables found`);
        continue;
      }

      // Build a single TRUNCATE statement for all tables in the schema
      const tableNames = result.rows
        .map((row) => `"${schema}"."${row.tablename}"`)
        .join(', ');

      await client.query(`TRUNCATE TABLE ${tableNames} CASCADE`);
      console.log(`  ${schema}: truncated ${result.rows.length} table(s)`);
    }

    // Also truncate public schema tables (if any test tables exist there)
    const publicTables = await client.query(
      `SELECT tablename FROM pg_tables
       WHERE schemaname = 'public'
       AND tablename NOT LIKE 'pg_%'
       AND tablename NOT LIKE '_prisma_%'`
    );

    if (publicTables.rows.length > 0) {
      const publicTableNames = publicTables.rows
        .map((row) => `"public"."${row.tablename}"`)
        .join(', ');

      await client.query(`TRUNCATE TABLE ${publicTableNames} CASCADE`);
      console.log(
        `  public: truncated ${publicTables.rows.length} table(s)`
      );
    }

    // Re-enable triggers
    await client.query(`SET session_replication_role = 'origin'`);

    const elapsed = Date.now() - startTime;
    console.log(`\nDatabase reset complete in ${elapsed}ms`);

    if (elapsed > 30000) {
      console.warn(`WARNING: Reset took ${elapsed}ms (target: <30000ms)`);
    }
  } catch (error) {
    console.error('Database reset failed:', error);
    throw error;
  } finally {
    if (client) {
      client.release();
    }
    await pool.end();
  }
}

// Export for use in test setup (beforeAll hooks)
export { resetDatabase };

// Run if called directly
if (require.main === module) {
  resetDatabase()
    .then(() => process.exit(0))
    .catch((error) => {
      console.error(error);
      process.exit(1);
    });
}
