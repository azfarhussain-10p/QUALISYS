# Story 0.14: Test Database Provisioning

Status: ready-for-dev

## Story

As a **QA Engineer**,
I want **a dedicated test database with proper isolation**,
so that **tests don't interfere with development or staging data and can run in parallel safely**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | Separate PostgreSQL database created: qualisys_test | psql \l shows qualisys_test database |
| AC2 | Test database accessible from CI/CD runners | GitHub Actions can connect and run queries |
| AC3 | Test database accessible from local development | Docker Compose connects to test DB |
| AC4 | Database reset mechanism for clean test runs | Reset script truncates/recreates tables |
| AC5 | Test tenant schemas created: tenant_test_1, tenant_test_2, tenant_test_3 | psql \dn shows test tenant schemas |
| AC6 | Test database connection string stored in secrets | GitHub Secrets contains TEST_DATABASE_URL |
| AC7 | Isolation verification: tenant_test_1 cannot access tenant_test_2 data | RLS policy test passes |
| AC8 | Test database user has appropriate permissions (not superuser) | pg_roles shows test_user without superuser |
| AC9 | Database migrations run successfully on test database | Migration script completes without errors |
| AC10 | Test database performance comparable to production config | Query execution times within 2x of production |

## Tasks / Subtasks

- [ ] **Task 1: Test Database Creation** (AC: 1, 8)
  - [ ] 1.1 Create qualisys_test database in RDS instance
  - [ ] 1.2 Create test_user role with limited permissions
  - [ ] 1.3 Configure test_user with schema creation privileges
  - [ ] 1.4 Verify test_user is NOT superuser, NOT bypassrls
  - [ ] 1.5 Document test database credentials

- [ ] **Task 2: Test Tenant Schemas** (AC: 5, 7)
  - [ ] 2.1 Create schema provisioning script for test tenants
  - [ ] 2.2 Create tenant_test_1, tenant_test_2, tenant_test_3 schemas
  - [ ] 2.3 Apply RLS policies to test tenant tables
  - [ ] 2.4 Create isolation verification test script
  - [ ] 2.5 Run isolation tests to verify RLS working

- [ ] **Task 3: Connection Configuration** (AC: 2, 3, 6)
  - [ ] 3.1 Store test database connection string in AWS Secrets Manager
  - [ ] 3.2 Add TEST_DATABASE_URL to GitHub Actions secrets
  - [ ] 3.3 Configure Docker Compose to use test database
  - [ ] 3.4 Create .env.test template for local development
  - [ ] 3.5 Document connection methods for different environments

- [ ] **Task 4: Database Reset Mechanism** (AC: 4, 9)
  - [ ] 4.1 Create database reset script (truncate all tables)
  - [ ] 4.2 Create schema recreation script (drop and recreate)
  - [ ] 4.3 Integrate reset into test setup (beforeAll hook)
  - [ ] 4.4 Configure reset to preserve schema structure
  - [ ] 4.5 Add reset command to package.json scripts

- [ ] **Task 5: Migration Support** (AC: 9, 10)
  - [ ] 5.1 Configure migration tool to target test database
  - [ ] 5.2 Create test-specific migration script
  - [ ] 5.3 Verify all migrations apply successfully
  - [ ] 5.4 Add migration step to CI/CD test job
  - [ ] 5.5 Document migration workflow for test database

- [ ] **Task 6: Validation & Documentation** (AC: All)
  - [ ] 6.1 Run full test suite against test database
  - [ ] 6.2 Verify CI/CD pipeline uses test database
  - [ ] 6.3 Test local development workflow
  - [ ] 6.4 Performance benchmark test database
  - [ ] 6.5 Document test database setup in CONTRIBUTING.md

## Dev Notes

### Architecture Alignment

This story implements test database infrastructure per the architecture document:

- **Test Isolation**: Dedicated database prevents test/dev data conflicts
- **Multi-Tenant Testing**: Test schemas validate RLS policies
- **CI/CD Integration**: Automated tests run against consistent database
- **Parallel Safety**: Multiple test runs can use separate schemas

### Technical Constraints

- **No Superuser**: Test user must NOT have superuser privileges
- **No RLS Bypass**: Test user must NOT have bypassrls privilege
- **Isolation Required**: RLS policies must prevent cross-tenant access
- **Reset Speed**: Database reset must complete in <30 seconds
- **Same Schema**: Test database schema must match production exactly

### Database Configuration

```sql
-- Create test database
CREATE DATABASE qualisys_test;

-- Connect to test database
\c qualisys_test

-- Create test user (NO SUPERUSER, NO BYPASSRLS)
CREATE ROLE test_user WITH LOGIN PASSWORD 'stored_in_secrets_manager';
GRANT CREATE ON DATABASE qualisys_test TO test_user;
GRANT USAGE ON SCHEMA public TO test_user;

-- Verify test_user permissions (CRITICAL)
SELECT rolname, rolsuper, rolbypassrls
FROM pg_roles
WHERE rolname = 'test_user';
-- Expected: rolsuper=f, rolbypassrls=f
```

### Test Tenant Schema Creation

```sql
-- Create test tenant schemas
CREATE SCHEMA IF NOT EXISTS tenant_test_1;
CREATE SCHEMA IF NOT EXISTS tenant_test_2;
CREATE SCHEMA IF NOT EXISTS tenant_test_3;

-- Grant test_user access to schemas
GRANT ALL ON SCHEMA tenant_test_1 TO test_user;
GRANT ALL ON SCHEMA tenant_test_2 TO test_user;
GRANT ALL ON SCHEMA tenant_test_3 TO test_user;

-- Example table with RLS (applied to all tenant tables)
CREATE TABLE tenant_test_1.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Enable RLS
ALTER TABLE tenant_test_1.projects ENABLE ROW LEVEL SECURITY;

-- Create RLS policy
CREATE POLICY tenant_isolation ON tenant_test_1.projects
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Force RLS for table owner too
ALTER TABLE tenant_test_1.projects FORCE ROW LEVEL SECURITY;
```

### Isolation Verification Script

```sql
-- isolation_test.sql
-- This script verifies that RLS policies prevent cross-tenant access

-- Set tenant context to tenant_test_1
SET LOCAL app.current_tenant = '11111111-1111-1111-1111-111111111111';

-- Insert data as tenant_test_1
INSERT INTO tenant_test_1.projects (tenant_id, name)
VALUES ('11111111-1111-1111-1111-111111111111', 'Tenant 1 Project');

-- Switch to tenant_test_2 context
SET LOCAL app.current_tenant = '22222222-2222-2222-2222-222222222222';

-- Attempt to read tenant_test_1 data (should return 0 rows)
SELECT COUNT(*) FROM tenant_test_1.projects;
-- Expected: 0 (RLS blocks access)

-- Attempt to insert with wrong tenant_id (should fail or be invisible)
INSERT INTO tenant_test_1.projects (tenant_id, name)
VALUES ('22222222-2222-2222-2222-222222222222', 'Tenant 2 Project');

-- Verify tenant 2 cannot see tenant 1 data
SET LOCAL app.current_tenant = '11111111-1111-1111-1111-111111111111';
SELECT COUNT(*) FROM tenant_test_1.projects WHERE name = 'Tenant 1 Project';
-- Expected: 1

SET LOCAL app.current_tenant = '22222222-2222-2222-2222-222222222222';
SELECT COUNT(*) FROM tenant_test_1.projects WHERE name = 'Tenant 1 Project';
-- Expected: 0
```

### Database Reset Script

```typescript
// scripts/db-reset.ts
import { Pool } from 'pg';

const pool = new Pool({
  connectionString: process.env.TEST_DATABASE_URL,
});

async function resetDatabase(): Promise<void> {
  const client = await pool.connect();

  try {
    // Get all tables in test tenant schemas
    const schemas = ['tenant_test_1', 'tenant_test_2', 'tenant_test_3'];

    for (const schema of schemas) {
      // Disable triggers temporarily
      await client.query(`SET session_replication_role = 'replica'`);

      // Get all tables in schema
      const tables = await client.query(`
        SELECT tablename FROM pg_tables WHERE schemaname = $1
      `, [schema]);

      // Truncate all tables
      for (const row of tables.rows) {
        await client.query(`TRUNCATE TABLE ${schema}.${row.tablename} CASCADE`);
      }

      // Re-enable triggers
      await client.query(`SET session_replication_role = 'origin'`);
    }

    console.log('Database reset complete');
  } finally {
    client.release();
  }
}

resetDatabase().catch(console.error);
```

### Connection String Format

```
# Production/Staging (from Story 0.4)
DATABASE_URL=postgresql://app_user:password@qualisys-db.cluster-xxx.us-east-1.rds.amazonaws.com:5432/qualisys_master

# Test Database
TEST_DATABASE_URL=postgresql://test_user:password@qualisys-db.cluster-xxx.us-east-1.rds.amazonaws.com:5432/qualisys_test

# Local Development (Docker Compose)
TEST_DATABASE_URL=postgresql://test_user:test_password@localhost:5433/qualisys_test
```

### Docker Compose Test Database

```yaml
# docker-compose.yml (test database service)
services:
  postgres-test:
    image: postgres:15-alpine
    container_name: qualisys-postgres-test
    environment:
      POSTGRES_DB: qualisys_test
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
    ports:
      - "5433:5432"  # Different port to avoid conflict
    volumes:
      - postgres-test-data:/var/lib/postgresql/data
      - ./scripts/init-test-db.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test_user -d qualisys_test"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres-test-data:
```

### CI/CD Integration

```yaml
# In .github/workflows/pr-checks.yml
jobs:
  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: qualisys_test
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm run db:migrate:test
        env:
          TEST_DATABASE_URL: postgresql://test_user:test_password@localhost:5432/qualisys_test
      - run: npm run test:integration
        env:
          TEST_DATABASE_URL: postgresql://test_user:test_password@localhost:5432/qualisys_test
```

### Package.json Scripts

```json
{
  "scripts": {
    "db:migrate:test": "DATABASE_URL=$TEST_DATABASE_URL npx prisma migrate deploy",
    "db:reset:test": "ts-node scripts/db-reset.ts",
    "db:seed:test": "DATABASE_URL=$TEST_DATABASE_URL ts-node scripts/seed-test.ts",
    "test:integration": "jest --config jest.integration.config.js",
    "test:integration:watch": "jest --config jest.integration.config.js --watch"
  }
}
```

### Project Structure Notes

```
/
├── scripts/
│   ├── db-reset.ts              # Database reset script
│   ├── init-test-db.sql         # Test database initialization
│   ├── create-test-tenants.sql  # Test tenant schema creation
│   ├── isolation-test.sql       # RLS isolation verification
│   └── seed-test.ts             # Test data seeding
├── docker-compose.yml           # Updated with test database service
├── .env.test.example            # Test environment template
├── jest.integration.config.js   # Integration test configuration
└── CONTRIBUTING.md              # Updated with test database docs
```

### Dependencies

- **Story 0.4** (PostgreSQL Database) - REQUIRED: RDS instance to host test database
- Outputs used by subsequent stories:
  - Story 0.10 (Automated Tests): Test database for integration tests
  - Story 0.15 (Test Data Factories): Database for seeding test data
  - Story 0.16 (CI/CD Test Pipeline): Database connection for CI/CD
  - Story 0.18 (Multi-Tenant Test Isolation): Tenant isolation verification

### Security Considerations

1. **Threat: Test user privilege escalation** → Verify NO SUPERUSER, NO BYPASSRLS
2. **Threat: Test data leaks to production** → Separate database, separate credentials
3. **Threat: RLS bypass in tests** → Run isolation verification tests
4. **Threat: Credential exposure** → Store in Secrets Manager, not in code
5. **Threat: Test DB accessible from internet** → Security group restricts to VPC only

### Performance Considerations

- Test database uses same instance class as staging for realistic performance
- Connection pooling configured to handle parallel test execution
- Reset script optimized to complete in <30 seconds
- Indexes maintained same as production for accurate query performance

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#Data-Models-and-Contracts]
- [Source: docs/tech-specs/tech-spec-epic-0.md#Security]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.14]
- [Source: docs/architecture/architecture.md#Multi-Tenant-Database]

## Dev Agent Record

### Context Reference

- [docs/stories/0-14-test-database-provisioning.context.xml](./0-14-test-database-provisioning.context.xml)

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
