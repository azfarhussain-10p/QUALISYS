# Story 0.15: Test Data Factories & Seeding

Status: ready-for-dev

## Story

As a **QA Engineer**,
I want **test data factories to generate realistic test data**,
so that **tests are consistent, repeatable, and reflect real-world scenarios**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | Test data factory library configured (Faker.js) | Package.json includes faker dependency |
| AC2 | User factory creates users with roles (admin, member, viewer) | Factory generates valid user objects |
| AC3 | Organization factory creates orgs with tenant schemas | Factory generates org with tenant_id |
| AC4 | Project factory creates projects with configurations | Factory generates project linked to org |
| AC5 | Test case factory creates test cases with steps | Factory generates test case with steps array |
| AC6 | Test execution factory creates execution records | Factory generates execution with results |
| AC7 | Seed script creates baseline test data (3 tenants, 10 users, 5 projects) | Seed script populates database successfully |
| AC8 | Factories support associations (user belongs to organization) | Related entities created with proper foreign keys |
| AC9 | Seed script is idempotent (can run multiple times safely) | Running seed twice doesn't create duplicates |
| AC10 | Seed data documented in README (what data exists, how to reset) | Documentation describes seed data structure |

## Tasks / Subtasks

- [ ] **Task 1: Factory Library Setup** (AC: 1)
  - [ ] 1.1 Install @faker-js/faker package
  - [ ] 1.2 Create factories directory structure
  - [ ] 1.3 Create base factory class/utility
  - [ ] 1.4 Configure TypeScript types for factories
  - [ ] 1.5 Add factory exports to index file

- [ ] **Task 2: Core Entity Factories** (AC: 2, 3, 4)
  - [ ] 2.1 Create UserFactory with role support
  - [ ] 2.2 Create OrganizationFactory with tenant schema
  - [ ] 2.3 Create ProjectFactory linked to organization
  - [ ] 2.4 Create TeamFactory for team membership
  - [ ] 2.5 Add factory customization options (overrides)

- [ ] **Task 3: Testing Entity Factories** (AC: 5, 6)
  - [ ] 3.1 Create TestCaseFactory with steps
  - [ ] 3.2 Create TestSuiteFactory grouping test cases
  - [ ] 3.3 Create TestExecutionFactory with results
  - [ ] 3.4 Create TestEvidenceFactory (screenshots, videos)
  - [ ] 3.5 Create DefectFactory linked to test executions

- [ ] **Task 4: Association Support** (AC: 8)
  - [ ] 4.1 Implement belongsTo relationship helper
  - [ ] 4.2 Implement hasMany relationship helper
  - [ ] 4.3 Create composite factory for full entity graphs
  - [ ] 4.4 Handle circular dependencies properly
  - [ ] 4.5 Add transaction support for related inserts

- [ ] **Task 5: Seed Script** (AC: 7, 9)
  - [ ] 5.1 Create seed.ts main script
  - [ ] 5.2 Implement idempotent upsert logic
  - [ ] 5.3 Create 3 test tenants with schemas
  - [ ] 5.4 Create 10 users across tenants
  - [ ] 5.5 Create 5 projects with test data
  - [ ] 5.6 Add npm script for seeding

- [ ] **Task 6: Documentation** (AC: 10)
  - [ ] 6.1 Document factory usage examples
  - [ ] 6.2 Document seed data structure
  - [ ] 6.3 Add factory API reference
  - [ ] 6.4 Document reset and reseed process
  - [ ] 6.5 Update CONTRIBUTING.md with test data guide

## Dev Notes

### Architecture Alignment

This story implements test data factories per the architecture document:

- **Consistent Testing**: Factories ensure predictable test data
- **Realistic Data**: Faker generates production-like values
- **Multi-Tenant Support**: Factories respect tenant boundaries
- **Fast Setup**: Seed script provides baseline data quickly

### Technical Constraints

- **Idempotent Seeding**: Running seed multiple times must be safe
- **Tenant Isolation**: Factory data must respect schema boundaries
- **Foreign Key Integrity**: Associations must maintain referential integrity
- **Type Safety**: Factories must return properly typed objects
- **Performance**: Seed script should complete in <60 seconds

### Factory Library Structure

```typescript
// factories/index.ts
export { UserFactory } from './UserFactory';
export { OrganizationFactory } from './OrganizationFactory';
export { ProjectFactory } from './ProjectFactory';
export { TestCaseFactory } from './TestCaseFactory';
export { TestExecutionFactory } from './TestExecutionFactory';
export { createTestTenant } from './helpers';
```

### User Factory

```typescript
// factories/UserFactory.ts
import { faker } from '@faker-js/faker';
import { User, UserRole } from '../types';

interface UserFactoryOptions {
  organizationId?: string;
  role?: UserRole;
  email?: string;
  isActive?: boolean;
}

export class UserFactory {
  static create(options: UserFactoryOptions = {}): User {
    return {
      id: faker.string.uuid(),
      email: options.email ?? faker.internet.email(),
      firstName: faker.person.firstName(),
      lastName: faker.person.lastName(),
      role: options.role ?? 'member',
      organizationId: options.organizationId ?? faker.string.uuid(),
      isActive: options.isActive ?? true,
      createdAt: faker.date.past(),
      updatedAt: new Date(),
    };
  }

  static createMany(count: number, options: UserFactoryOptions = {}): User[] {
    return Array.from({ length: count }, () => this.create(options));
  }

  static async createAndSave(
    db: Database,
    options: UserFactoryOptions = {}
  ): Promise<User> {
    const user = this.create(options);
    await db.users.insert(user);
    return user;
  }
}
```

### Organization Factory

```typescript
// factories/OrganizationFactory.ts
import { faker } from '@faker-js/faker';
import { Organization } from '../types';

interface OrganizationFactoryOptions {
  name?: string;
  plan?: 'free' | 'pro' | 'enterprise';
  tenantId?: string;
}

export class OrganizationFactory {
  static create(options: OrganizationFactoryOptions = {}): Organization {
    const tenantId = options.tenantId ?? faker.string.uuid();
    return {
      id: faker.string.uuid(),
      name: options.name ?? faker.company.name(),
      slug: faker.helpers.slugify(options.name ?? faker.company.name()).toLowerCase(),
      tenantId,
      schemaName: `tenant_${tenantId.replace(/-/g, '_').substring(0, 8)}`,
      plan: options.plan ?? 'free',
      settings: {
        maxUsers: options.plan === 'enterprise' ? 100 : options.plan === 'pro' ? 25 : 5,
        maxProjects: options.plan === 'enterprise' ? 50 : options.plan === 'pro' ? 10 : 2,
      },
      createdAt: faker.date.past(),
      updatedAt: new Date(),
    };
  }

  static async createWithSchema(db: Database): Promise<Organization> {
    const org = this.create();
    await db.query(`CREATE SCHEMA IF NOT EXISTS ${org.schemaName}`);
    await db.organizations.insert(org);
    return org;
  }
}
```

### Test Case Factory

```typescript
// factories/TestCaseFactory.ts
import { faker } from '@faker-js/faker';
import { TestCase, TestStep } from '../types';

interface TestCaseFactoryOptions {
  projectId?: string;
  stepsCount?: number;
  priority?: 'low' | 'medium' | 'high' | 'critical';
}

export class TestCaseFactory {
  static create(options: TestCaseFactoryOptions = {}): TestCase {
    const stepsCount = options.stepsCount ?? faker.number.int({ min: 3, max: 10 });

    return {
      id: faker.string.uuid(),
      projectId: options.projectId ?? faker.string.uuid(),
      title: faker.lorem.sentence(),
      description: faker.lorem.paragraph(),
      priority: options.priority ?? faker.helpers.arrayElement(['low', 'medium', 'high', 'critical']),
      status: 'active',
      steps: this.createSteps(stepsCount),
      tags: faker.helpers.arrayElements(['smoke', 'regression', 'e2e', 'api', 'ui'], 2),
      estimatedDuration: faker.number.int({ min: 60, max: 600 }), // seconds
      createdAt: faker.date.past(),
      updatedAt: new Date(),
    };
  }

  private static createSteps(count: number): TestStep[] {
    return Array.from({ length: count }, (_, index) => ({
      id: faker.string.uuid(),
      order: index + 1,
      action: faker.lorem.sentence(),
      expectedResult: faker.lorem.sentence(),
      data: faker.datatype.boolean() ? { input: faker.lorem.word() } : undefined,
    }));
  }
}
```

### Test Execution Factory

```typescript
// factories/TestExecutionFactory.ts
import { faker } from '@faker-js/faker';
import { TestExecution, ExecutionStatus } from '../types';

interface TestExecutionFactoryOptions {
  testCaseId?: string;
  status?: ExecutionStatus;
  executedBy?: string;
}

export class TestExecutionFactory {
  static create(options: TestExecutionFactoryOptions = {}): TestExecution {
    const status = options.status ?? faker.helpers.arrayElement(['passed', 'failed', 'skipped', 'blocked']);
    const startTime = faker.date.recent();
    const duration = faker.number.int({ min: 10, max: 300 });

    return {
      id: faker.string.uuid(),
      testCaseId: options.testCaseId ?? faker.string.uuid(),
      status,
      executedBy: options.executedBy ?? faker.string.uuid(),
      startTime,
      endTime: new Date(startTime.getTime() + duration * 1000),
      duration,
      environment: faker.helpers.arrayElement(['staging', 'production', 'local']),
      browser: faker.helpers.arrayElement(['chrome', 'firefox', 'safari', 'edge']),
      notes: status === 'failed' ? faker.lorem.sentence() : undefined,
      errorMessage: status === 'failed' ? faker.lorem.paragraph() : undefined,
      screenshots: status === 'failed' ? [faker.system.filePath()] : [],
      createdAt: new Date(),
    };
  }
}
```

### Seed Script

```typescript
// scripts/seed.ts
import { Pool } from 'pg';
import { faker } from '@faker-js/faker';
import {
  UserFactory,
  OrganizationFactory,
  ProjectFactory,
  TestCaseFactory,
} from '../factories';

const pool = new Pool({
  connectionString: process.env.TEST_DATABASE_URL,
});

// Fixed UUIDs for idempotent seeding
const SEED_TENANTS = [
  { id: '11111111-1111-1111-1111-111111111111', name: 'Acme Corp' },
  { id: '22222222-2222-2222-2222-222222222222', name: 'Globex Inc' },
  { id: '33333333-3333-3333-3333-333333333333', name: 'Initech LLC' },
];

async function seed(): Promise<void> {
  const client = await pool.connect();

  try {
    await client.query('BEGIN');

    // Create organizations (idempotent with ON CONFLICT)
    for (const tenant of SEED_TENANTS) {
      const org = OrganizationFactory.create({
        name: tenant.name,
        tenantId: tenant.id,
      });

      await client.query(`
        INSERT INTO organizations (id, name, slug, tenant_id, schema_name, plan, settings, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (tenant_id) DO UPDATE SET
          name = EXCLUDED.name,
          updated_at = NOW()
      `, [org.id, org.name, org.slug, org.tenantId, org.schemaName, org.plan, org.settings, org.createdAt]);

      // Create schema if not exists
      await client.query(`CREATE SCHEMA IF NOT EXISTS ${org.schemaName}`);

      // Create users for this tenant
      const users = UserFactory.createMany(3, { organizationId: org.id });
      // Make first user admin
      users[0].role = 'admin';

      for (const user of users) {
        await client.query(`
          INSERT INTO ${org.schemaName}.users (id, email, first_name, last_name, role, organization_id, is_active, created_at)
          VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
          ON CONFLICT (email) DO UPDATE SET
            first_name = EXCLUDED.first_name,
            updated_at = NOW()
        `, [user.id, user.email, user.firstName, user.lastName, user.role, user.organizationId, user.isActive, user.createdAt]);
      }

      // Create projects for this tenant
      const projectCount = tenant.id === SEED_TENANTS[0].id ? 3 : 1;
      for (let i = 0; i < projectCount; i++) {
        const project = ProjectFactory.create({ organizationId: org.id });
        await client.query(`
          INSERT INTO ${org.schemaName}.projects (id, name, description, organization_id, created_at)
          VALUES ($1, $2, $3, $4, $5)
          ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            updated_at = NOW()
        `, [project.id, project.name, project.description, project.organizationId, project.createdAt]);

        // Create test cases for this project
        const testCases = Array.from({ length: 5 }, () =>
          TestCaseFactory.create({ projectId: project.id })
        );

        for (const tc of testCases) {
          await client.query(`
            INSERT INTO ${org.schemaName}.test_cases (id, project_id, title, description, priority, steps, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE SET
              title = EXCLUDED.title,
              updated_at = NOW()
          `, [tc.id, tc.projectId, tc.title, tc.description, tc.priority, JSON.stringify(tc.steps), tc.createdAt]);
        }
      }
    }

    await client.query('COMMIT');
    console.log('Seed completed successfully!');
    console.log(`Created: 3 tenants, 9 users, 5 projects, 25 test cases`);

  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
    await pool.end();
  }
}

seed().catch((error) => {
  console.error('Seed failed:', error);
  process.exit(1);
});
```

### Project Factory

```typescript
// factories/ProjectFactory.ts
import { faker } from '@faker-js/faker';
import { Project } from '../types';

interface ProjectFactoryOptions {
  organizationId?: string;
  name?: string;
}

export class ProjectFactory {
  static create(options: ProjectFactoryOptions = {}): Project {
    return {
      id: faker.string.uuid(),
      name: options.name ?? `${faker.commerce.productAdjective()} ${faker.commerce.product()} Tests`,
      description: faker.lorem.paragraph(),
      organizationId: options.organizationId ?? faker.string.uuid(),
      settings: {
        defaultBrowser: 'chrome',
        parallelExecutions: 5,
        retryCount: 2,
      },
      isActive: true,
      createdAt: faker.date.past(),
      updatedAt: new Date(),
    };
  }
}
```

### Package.json Scripts

```json
{
  "scripts": {
    "db:seed": "ts-node scripts/seed.ts",
    "db:seed:test": "TEST_DATABASE_URL=$TEST_DATABASE_URL ts-node scripts/seed.ts",
    "db:fresh": "npm run db:reset:test && npm run db:migrate:test && npm run db:seed:test",
    "test:with-seed": "npm run db:fresh && npm run test:integration"
  }
}
```

### Project Structure Notes

```
/
├── factories/
│   ├── index.ts                 # Factory exports
│   ├── UserFactory.ts           # User factory
│   ├── OrganizationFactory.ts   # Organization factory
│   ├── ProjectFactory.ts        # Project factory
│   ├── TestCaseFactory.ts       # Test case factory
│   ├── TestExecutionFactory.ts  # Test execution factory
│   └── helpers.ts               # Association helpers
├── scripts/
│   ├── seed.ts                  # Main seed script
│   └── seed-data.json           # Fixed seed data (optional)
├── types/
│   └── entities.ts              # TypeScript entity types
└── CONTRIBUTING.md              # Updated with factory/seed docs
```

### Dependencies

- **Story 0.14** (Test Database) - REQUIRED: Database to seed
- Outputs used by subsequent stories:
  - Story 0.16 (CI/CD Test Pipeline): Seed data for integration tests
  - Story 0.18 (Multi-Tenant Test Isolation): Tenant-aware test data
  - Epic 1-5: Factory patterns for feature tests

### Documentation Template

```markdown
## Test Data Factories

### Quick Start

```bash
# Seed the test database
npm run db:seed:test

# Fresh database with seed data
npm run db:fresh
```

### Available Factories

| Factory | Description | Example |
|---------|-------------|---------|
| UserFactory | Creates user entities | `UserFactory.create({ role: 'admin' })` |
| OrganizationFactory | Creates org with tenant | `OrganizationFactory.create({ plan: 'pro' })` |
| ProjectFactory | Creates project | `ProjectFactory.create({ organizationId })` |
| TestCaseFactory | Creates test with steps | `TestCaseFactory.create({ stepsCount: 5 })` |
| TestExecutionFactory | Creates execution record | `TestExecutionFactory.create({ status: 'passed' })` |

### Seed Data Structure

After running `npm run db:seed:test`:

- **3 Tenants**: Acme Corp, Globex Inc, Initech LLC
- **9 Users**: 3 per tenant (1 admin, 2 members)
- **5 Projects**: 3 in Acme, 1 in Globex, 1 in Initech
- **25 Test Cases**: 5 per project

### Idempotent Seeding

The seed script uses `ON CONFLICT DO UPDATE` to safely re-run:
- Existing records are updated, not duplicated
- New records are inserted
- Run `npm run db:seed:test` anytime to refresh data
```

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#Test-Infrastructure]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.15]
- [Source: docs/architecture/architecture.md#Testing-Strategy]
- [Source: docs/test-design-system.md#Test-Data-Management]

## Dev Agent Record

### Context Reference

- [docs/stories/0-15-test-data-factories-seeding.context.xml](./0-15-test-data-factories-seeding.context.xml)

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

### File List

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-01-23 | SM Agent (Bob) | Story drafted from Epic 0 tech spec and epic file |
| 2026-01-23 | SM Agent (Bob) | Context XML generated, status: drafted → ready-for-dev |
