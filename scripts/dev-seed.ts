/**
 * Local Development Database Seed Script
 * Story: 0-21 Local Development Environment (Podman Compose)
 * AC: 9  - Seed data populates local database
 *
 * Seeds the local development database (qualisys_master) with sample data.
 * Separate from scripts/seed.ts (Story 0-15) which seeds the TEST database.
 *
 * Usage:
 *   npx ts-node scripts/dev-seed.ts
 *   podman-compose exec api npx ts-node scripts/dev-seed.ts
 *
 * Environment:
 *   DATABASE_URL - PostgreSQL connection (defaults to local compose)
 *
 * Test credentials after seeding:
 *   Email:    admin@tenant-dev-1.test
 *   Password: password123
 */

import { Pool, PoolClient } from 'pg';
import { faker } from '@faker-js/faker';

// Fixed seed for deterministic data across runs
faker.seed(21);

const DEV_TENANTS = [
  {
    tenantId: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    orgName: 'Dev Organization Alpha',
    orgSlug: 'dev-org-alpha',
    schema: 'tenant_dev_1',
    plan: 'enterprise',
    userCount: 6,
    projectCount: 3,
  },
  {
    tenantId: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    orgName: 'Dev Organization Beta',
    orgSlug: 'dev-org-beta',
    schema: 'tenant_dev_2',
    plan: 'free',
    userCount: 3,
    projectCount: 1,
  },
];

const DEFAULT_PASSWORD_HASH =
  '$2b$10$K4GH7yjN0yRKN1VYhKQpCOqNlC7.w5fMuAJjxQoJAqT1JjPq1yUzS'; // bcrypt("password123")

// =============================================================================
// Seed Functions
// =============================================================================

async function seedOrganization(
  client: PoolClient,
  tenant: (typeof DEV_TENANTS)[0]
): Promise<string> {
  const orgId = faker.string.uuid();

  await client.query(
    `INSERT INTO public.organizations (id, name, slug, tenant_id, schema_name, plan)
     VALUES ($1, $2, $3, $4, $5, $6)
     ON CONFLICT (tenant_id) DO UPDATE SET
       name = EXCLUDED.name,
       slug = EXCLUDED.slug,
       plan = EXCLUDED.plan,
       updated_at = NOW()`,
    [orgId, tenant.orgName, tenant.orgSlug, tenant.tenantId, tenant.schema, tenant.plan]
  );

  return orgId;
}

async function seedUsers(
  client: PoolClient,
  schema: string,
  orgId: string,
  tenantId: string,
  count: number
): Promise<string[]> {
  const userIds: string[] = [];

  // Admin user (deterministic)
  const adminId = faker.string.uuid();
  await client.query(
    `INSERT INTO "${schema}".users
       (id, tenant_id, email, password_hash, first_name, last_name, role, organization_id, is_active)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, true)
     ON CONFLICT (email) DO UPDATE SET
       password_hash = EXCLUDED.password_hash,
       role = EXCLUDED.role,
       updated_at = NOW()`,
    [
      adminId,
      tenantId,
      `admin@${schema.replaceAll('_', '-')}.test`,
      DEFAULT_PASSWORD_HASH,
      'Admin',
      'User',
      'admin',
      orgId,
    ]
  );
  userIds.push(adminId);

  // Additional users
  for (let i = 1; i < count; i++) {
    const userId = faker.string.uuid();
    const firstName = faker.person.firstName();
    const lastName = faker.person.lastName();
    await client.query(
      `INSERT INTO "${schema}".users
         (id, tenant_id, email, password_hash, first_name, last_name, role, organization_id, is_active)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, true)
       ON CONFLICT (email) DO UPDATE SET
         first_name = EXCLUDED.first_name,
         last_name = EXCLUDED.last_name,
         updated_at = NOW()`,
      [
        userId,
        tenantId,
        faker.internet.email({ firstName, lastName }).toLowerCase(),
        DEFAULT_PASSWORD_HASH,
        firstName,
        lastName,
        faker.helpers.arrayElement(['member', 'viewer']),
        orgId,
      ]
    );
    userIds.push(userId);
  }

  return userIds;
}

async function seedProjects(
  client: PoolClient,
  schema: string,
  tenantId: string,
  orgId: string,
  count: number,
  userIds: string[]
): Promise<void> {
  for (let i = 0; i < count; i++) {
    const projectId = faker.string.uuid();
    const projectName = faker.commerce.productName();

    await client.query(
      `INSERT INTO "${schema}".projects
         (id, name, description, organization_id, tenant_id, settings, is_active)
       VALUES ($1, $2, $3, $4, $5, $6, true)
       ON CONFLICT (id) DO UPDATE SET
         name = EXCLUDED.name,
         description = EXCLUDED.description,
         updated_at = NOW()`,
      [
        projectId,
        projectName,
        faker.lorem.paragraph(),
        orgId,
        tenantId,
        JSON.stringify({ browser: 'chromium', environment: 'staging' }),
      ]
    );

    // Create test cases per project
    for (let j = 0; j < 5; j++) {
      const tcId = faker.string.uuid();
      await client.query(
        `INSERT INTO "${schema}".test_cases
           (id, tenant_id, project_id, title, description, priority, status, steps, tags)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
         ON CONFLICT (id) DO UPDATE SET
           title = EXCLUDED.title,
           updated_at = NOW()`,
        [
          tcId,
          tenantId,
          projectId,
          `${faker.hacker.verb()} ${faker.hacker.noun()} — ${projectName}`,
          faker.lorem.sentences(2),
          faker.helpers.arrayElement(['critical', 'high', 'medium', 'low']),
          'active',
          JSON.stringify([
            { step: 1, action: faker.hacker.phrase(), expected: 'Should succeed' },
            { step: 2, action: faker.hacker.phrase(), expected: 'Should display result' },
          ]),
          `{${faker.helpers.arrayElement(['smoke', 'regression', 'sanity'])},${faker.helpers.arrayElement(['api', 'ui', 'integration'])}}`,
        ]
      );

      // One execution per test case
      const execId = faker.string.uuid();
      const status = faker.helpers.arrayElement(['passed', 'passed', 'passed', 'failed', 'skipped']);
      await client.query(
        `INSERT INTO "${schema}".test_executions
           (id, tenant_id, test_case_id, status, executed_by, start_time, end_time, duration, environment, browser)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
         ON CONFLICT (id) DO UPDATE SET
           status = EXCLUDED.status`,
        [
          execId,
          tenantId,
          tcId,
          status,
          userIds[0],
          faker.date.recent({ days: 7 }),
          faker.date.recent({ days: 1 }),
          faker.number.int({ min: 500, max: 30000 }),
          'staging',
          faker.helpers.arrayElement(['chromium', 'firefox', 'webkit']),
        ]
      );
    }
  }
}

// =============================================================================
// Main
// =============================================================================

async function devSeed(): Promise<void> {
  const connectionString =
    process.env.DATABASE_URL ||
    'postgresql://qualisys:qualisys_dev@localhost:5432/qualisys_master';

  // Safety check: refuse to seed production
  if (connectionString.includes('production') || connectionString.includes('prod.')) {
    console.error('ERROR: Refusing to seed a production database!');
    process.exit(1);
  }

  const pool = new Pool({ connectionString });
  let client: PoolClient | null = null;
  const startTime = Date.now();

  try {
    client = await pool.connect();
    console.log('Starting local development seed...');

    await client.query('BEGIN');

    for (const tenant of DEV_TENANTS) {
      console.log(`  Seeding ${tenant.orgName} (${tenant.schema})...`);

      const orgId = await seedOrganization(client, tenant);
      const userIds = await seedUsers(client, tenant.schema, orgId, tenant.tenantId, tenant.userCount);
      await seedProjects(client, tenant.schema, tenant.tenantId, orgId, tenant.projectCount, userIds);

      console.log(
        `    ${tenant.userCount} users, ${tenant.projectCount} projects, ${tenant.projectCount * 5} test cases`
      );
    }

    await client.query('COMMIT');

    const elapsed = Date.now() - startTime;
    console.log(`\nDev seed completed in ${elapsed}ms`);
    console.log('\nTest credentials:');
    console.log('  Email:    admin@tenant-dev-1.test');
    console.log('  Password: password123');
  } catch (error) {
    if (client) {
      await client.query('ROLLBACK');
    }
    console.error('Dev seed failed:', error);
    throw error;
  } finally {
    if (client) {
      client.release();
    }
    await pool.end();
  }
}

// Run if called directly
devSeed()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
