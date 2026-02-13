/**
 * Test Database Seed Script
 * Story: 0-15 Test Data Factories & Seeding
 * AC: 7  - Seed script creates baseline test data (3 tenants, 10 users, 5 projects)
 * AC: 9  - Seed script is idempotent (can run multiple times safely)
 *
 * Creates baseline test data using factories with ON CONFLICT DO UPDATE
 * for idempotent execution. Fixed UUIDs ensure consistent seed data.
 *
 * Usage:
 *   npm run db:seed:test
 *   npx ts-node scripts/seed.ts
 *
 * Environment:
 *   TEST_DATABASE_URL - PostgreSQL connection string for test database
 *
 * Performance target: <60 seconds
 */

import { Pool, PoolClient } from 'pg';
import { faker } from '@faker-js/faker';
import {
  UserFactory,
  OrganizationFactory,
  ProjectFactory,
  TestCaseFactory,
  TestExecutionFactory,
} from '../factories';

// =============================================================================
// Fixed Seed Data (deterministic UUIDs for idempotent seeding)
// =============================================================================

// Use a fixed seed so Faker generates consistent data across runs
faker.seed(42);

const SEED_TENANTS = [
  {
    tenantId: '11111111-1111-1111-1111-111111111111',
    orgName: 'Acme Corp',
    schema: 'tenant_test_1',
    projectCount: 3,
    userCount: 4,
  },
  {
    tenantId: '22222222-2222-2222-2222-222222222222',
    orgName: 'Globex Inc',
    schema: 'tenant_test_2',
    projectCount: 1,
    userCount: 3,
  },
  {
    tenantId: '33333333-3333-3333-3333-333333333333',
    orgName: 'Initech LLC',
    schema: 'tenant_test_3',
    projectCount: 1,
    userCount: 3,
  },
];

// =============================================================================
// Seed Functions
// =============================================================================

async function seedOrganization(
  client: PoolClient,
  tenant: (typeof SEED_TENANTS)[0]
): Promise<string> {
  const org = OrganizationFactory.create({
    name: tenant.orgName,
    tenantId: tenant.tenantId,
    schemaName: tenant.schema,
    plan: tenant.tenantId === SEED_TENANTS[0].tenantId ? 'enterprise' : 'free',
  });

  await client.query(
    `INSERT INTO public.organizations (id, name, slug, tenant_id, schema_name, plan, settings, created_at, updated_at)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
     ON CONFLICT (id) DO UPDATE SET
       name = EXCLUDED.name,
       slug = EXCLUDED.slug,
       plan = EXCLUDED.plan,
       settings = EXCLUDED.settings,
       updated_at = NOW()`,
    [
      org.id,
      org.name,
      org.slug,
      org.tenantId,
      org.schemaName,
      org.plan,
      JSON.stringify(org.settings),
      org.createdAt,
      org.updatedAt,
    ]
  );

  return org.id;
}

async function seedUsers(
  client: PoolClient,
  schema: string,
  orgId: string,
  tenantId: string,
  count: number
): Promise<string[]> {
  const users = UserFactory.createMany(count, { organizationId: orgId });
  // First user is always admin
  users[0] = { ...users[0], role: 'admin' };

  // Ensure table exists (created by init-test-db.sql or migrations)
  await client.query(`
    CREATE TABLE IF NOT EXISTS "${schema}".users (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id UUID NOT NULL DEFAULT '${tenantId}'::uuid,
      email VARCHAR(255) NOT NULL,
      first_name VARCHAR(255) NOT NULL,
      last_name VARCHAR(255) NOT NULL,
      role VARCHAR(50) NOT NULL DEFAULT 'member',
      organization_id UUID NOT NULL,
      is_active BOOLEAN NOT NULL DEFAULT true,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(email)
    )
  `);

  for (const user of users) {
    await client.query(
      `INSERT INTO "${schema}".users (id, tenant_id, email, first_name, last_name, role, organization_id, is_active, created_at, updated_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
       ON CONFLICT (email) DO UPDATE SET
         first_name = EXCLUDED.first_name,
         last_name = EXCLUDED.last_name,
         role = EXCLUDED.role,
         updated_at = NOW()`,
      [
        user.id,
        tenantId,
        user.email,
        user.firstName,
        user.lastName,
        user.role,
        user.organizationId,
        user.isActive,
        user.createdAt,
        user.updatedAt,
      ]
    );
  }

  return users.map((u) => u.id);
}

async function seedProjects(
  client: PoolClient,
  schema: string,
  orgId: string,
  tenantId: string,
  count: number,
  userIds: string[]
): Promise<void> {
  // Ensure projects table exists (may already exist from init-test-db.sql)
  await client.query(`
    CREATE TABLE IF NOT EXISTS "${schema}".projects (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id UUID NOT NULL DEFAULT '${tenantId}'::uuid,
      name VARCHAR(255) NOT NULL,
      description TEXT,
      organization_id UUID,
      settings JSONB DEFAULT '{}',
      is_active BOOLEAN NOT NULL DEFAULT true,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )
  `);

  // Ensure test_cases table exists
  await client.query(`
    CREATE TABLE IF NOT EXISTS "${schema}".test_cases (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id UUID NOT NULL DEFAULT '${tenantId}'::uuid,
      project_id UUID NOT NULL,
      title VARCHAR(500) NOT NULL,
      description TEXT,
      priority VARCHAR(50) NOT NULL DEFAULT 'medium',
      status VARCHAR(50) NOT NULL DEFAULT 'active',
      steps JSONB DEFAULT '[]',
      tags TEXT[] DEFAULT '{}',
      estimated_duration INTEGER DEFAULT 0,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )
  `);

  // Ensure test_executions table exists
  await client.query(`
    CREATE TABLE IF NOT EXISTS "${schema}".test_executions (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id UUID NOT NULL DEFAULT '${tenantId}'::uuid,
      test_case_id UUID NOT NULL,
      status VARCHAR(50) NOT NULL,
      executed_by UUID,
      start_time TIMESTAMP WITH TIME ZONE,
      end_time TIMESTAMP WITH TIME ZONE,
      duration INTEGER DEFAULT 0,
      environment VARCHAR(100),
      browser VARCHAR(100),
      notes TEXT,
      error_message TEXT,
      screenshots TEXT[] DEFAULT '{}',
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )
  `);

  for (let i = 0; i < count; i++) {
    const project = ProjectFactory.create({ organizationId: orgId });

    await client.query(
      `INSERT INTO "${schema}".projects (id, tenant_id, name, description, organization_id, settings, is_active, created_at, updated_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
       ON CONFLICT (id) DO UPDATE SET
         name = EXCLUDED.name,
         description = EXCLUDED.description,
         settings = EXCLUDED.settings,
         updated_at = NOW()`,
      [
        project.id,
        tenantId,
        project.name,
        project.description,
        project.organizationId,
        JSON.stringify(project.settings),
        project.isActive,
        project.createdAt,
        project.updatedAt,
      ]
    );

    // Create 5 test cases per project
    const testCases = TestCaseFactory.createMany(5, {
      projectId: project.id,
    });

    for (const tc of testCases) {
      await client.query(
        `INSERT INTO "${schema}".test_cases (id, tenant_id, project_id, title, description, priority, status, steps, tags, estimated_duration, created_at, updated_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
         ON CONFLICT (id) DO UPDATE SET
           title = EXCLUDED.title,
           steps = EXCLUDED.steps,
           updated_at = NOW()`,
        [
          tc.id,
          tenantId,
          tc.projectId,
          tc.title,
          tc.description,
          tc.priority,
          tc.status,
          JSON.stringify(tc.steps),
          tc.tags,
          tc.estimatedDuration,
          tc.createdAt,
          tc.updatedAt,
        ]
      );

      // Create 1 execution per test case
      const execution = TestExecutionFactory.create({
        testCaseId: tc.id,
        executedBy: userIds[0],
      });

      await client.query(
        `INSERT INTO "${schema}".test_executions (id, tenant_id, test_case_id, status, executed_by, start_time, end_time, duration, environment, browser, notes, error_message, screenshots, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
         ON CONFLICT (id) DO UPDATE SET
           status = EXCLUDED.status,
           end_time = EXCLUDED.end_time`,
        [
          execution.id,
          tenantId,
          execution.testCaseId,
          execution.status,
          execution.executedBy,
          execution.startTime,
          execution.endTime,
          execution.duration,
          execution.environment,
          execution.browser,
          execution.notes,
          execution.errorMessage,
          execution.screenshots,
          execution.createdAt,
        ]
      );
    }
  }
}

// =============================================================================
// Main Seed Function
// =============================================================================

async function seed(): Promise<void> {
  const connectionString = process.env.TEST_DATABASE_URL;

  if (!connectionString) {
    console.error('ERROR: TEST_DATABASE_URL environment variable is not set');
    process.exit(1);
  }

  // Safety check: refuse to seed production
  if (
    connectionString.includes('qualisys_master') ||
    connectionString.includes('production')
  ) {
    console.error('ERROR: Refusing to seed a production database!');
    process.exit(1);
  }

  const pool = new Pool({ connectionString });
  let client: PoolClient | null = null;
  const startTime = Date.now();

  try {
    client = await pool.connect();

    console.log('Starting test database seed...');

    // Ensure public.organizations table exists
    await client.query(`
      CREATE TABLE IF NOT EXISTS public.organizations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(255) NOT NULL,
        tenant_id UUID NOT NULL UNIQUE,
        schema_name VARCHAR(255) NOT NULL,
        plan VARCHAR(50) NOT NULL DEFAULT 'free',
        settings JSONB DEFAULT '{}',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
      )
    `);

    await client.query('BEGIN');

    let totalUsers = 0;
    let totalProjects = 0;
    let totalTestCases = 0;

    for (const tenant of SEED_TENANTS) {
      console.log(`  Seeding ${tenant.orgName} (${tenant.schema})...`);

      const orgId = await seedOrganization(client, tenant);
      const userIds = await seedUsers(
        client,
        tenant.schema,
        orgId,
        tenant.tenantId,
        tenant.userCount
      );
      await seedProjects(
        client,
        tenant.schema,
        orgId,
        tenant.tenantId,
        tenant.projectCount,
        userIds
      );

      totalUsers += tenant.userCount;
      totalProjects += tenant.projectCount;
      totalTestCases += tenant.projectCount * 5;
    }

    await client.query('COMMIT');

    const elapsed = Date.now() - startTime;
    console.log(`\nSeed completed in ${elapsed}ms`);
    console.log(
      `  3 tenants, ${totalUsers} users, ${totalProjects} projects, ${totalTestCases} test cases, ${totalTestCases} executions`
    );

    if (elapsed > 60000) {
      console.warn(`WARNING: Seed took ${elapsed}ms (target: <60000ms)`);
    }
  } catch (error) {
    if (client) {
      await client.query('ROLLBACK');
    }
    console.error('Seed failed:', error);
    throw error;
  } finally {
    if (client) {
      client.release();
    }
    await pool.end();
  }
}

// Export for use in test setup
export { seed };

// Run if called directly
if (require.main === module) {
  seed()
    .then(() => process.exit(0))
    .catch((error) => {
      console.error(error);
      process.exit(1);
    });
}
