-- =============================================================================
-- Test Database Initialization Script
-- Story: 0-14 Test Database Provisioning
-- AC: 1  - Separate PostgreSQL database created: qualisys_test
-- AC: 5  - Test tenant schemas created: tenant_test_1, tenant_test_2, tenant_test_3
-- AC: 7  - Isolation verification: tenant_test_1 cannot access tenant_test_2 data
-- AC: 8  - test_user with NO SUPERUSER, NO BYPASSRLS
--
-- USAGE (Managed PostgreSQL — RDS / Azure Flexible Server):
--   1. Connect as master admin:
--      PGPASSWORD=<master_password> psql \
--        -h <db_endpoint> -U qualisys_admin -d postgres \
--        -v test_user_password="'<test_user_password>'" \
--        -f infrastructure/scripts/init-test-db.sql
--
--   2. Or for local/CI (Docker/Podman):
--      Automatically run via docker-entrypoint-initdb.d mount
--
-- CRITICAL SECURITY CONSTRAINTS:
--   - test_user must NOT have SUPERUSER privileges
--   - test_user must NOT have BYPASSRLS privileges
--   - RLS policies must prevent cross-tenant data access
-- =============================================================================

-- =============================================================================
-- Step 1: Create test database (AC1)
-- =============================================================================

-- Note: CREATE DATABASE cannot run inside a transaction block.
-- When run via psql this works. When run via docker-entrypoint-initdb.d,
-- the POSTGRES_DB env var creates the database automatically.
SELECT 'Creating qualisys_test database...' AS status;

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'qualisys_test') THEN
    PERFORM dblink_exec('dbname=postgres', 'CREATE DATABASE qualisys_test');
    RAISE NOTICE 'Created database: qualisys_test';
  ELSE
    RAISE NOTICE 'Database qualisys_test already exists';
  END IF;
EXCEPTION
  WHEN undefined_function THEN
    RAISE NOTICE 'dblink not available — database should be created externally or via POSTGRES_DB env var';
END
$$;

-- =============================================================================
-- Step 2: Create test_user role (AC8)
-- CRITICAL: NO SUPERUSER, NO BYPASSRLS
-- =============================================================================

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'test_user') THEN
    CREATE ROLE test_user WITH
      LOGIN
      NOSUPERUSER
      NOBYPASSRLS
      NOCREATEDB
      NOCREATEROLE;
    RAISE NOTICE 'Created role: test_user';
  ELSE
    -- In Docker/CI, POSTGRES_USER creates test_user as SUPERUSER.
    -- Demote to enforce RLS in tests (CRITICAL for isolation verification).
    ALTER ROLE test_user WITH NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    RAISE NOTICE 'Role test_user exists — enforced NOSUPERUSER NOBYPASSRLS';
  END IF;
END
$$;

-- Set password (use psql variable for managed PostgreSQL, fallback for Docker)
-- For managed PostgreSQL: pass -v test_user_password="'actual_password'"
-- For Docker/CI: POSTGRES_PASSWORD env var handles this
DO $$
BEGIN
  -- Try to set password; in Docker context test_user IS the POSTGRES_USER
  ALTER ROLE test_user WITH PASSWORD 'test_password';
  RAISE NOTICE 'Set test_user password';
EXCEPTION
  WHEN insufficient_privilege THEN
    RAISE NOTICE 'Cannot set test_user password (may already be set by Docker)';
END
$$;

-- =============================================================================
-- Step 3: Grant test_user permissions (AC1, AC8)
-- =============================================================================

GRANT CREATE ON DATABASE qualisys_test TO test_user;
GRANT USAGE ON SCHEMA public TO test_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO test_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO test_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO test_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO test_user;

-- =============================================================================
-- Step 4: Verify test_user permissions (AC8)
-- =============================================================================

SELECT
  rolname,
  rolsuper,
  rolbypassrls,
  rolcreatedb,
  rolcreaterole,
  rolcanlogin
FROM pg_roles
WHERE rolname = 'test_user';
-- Expected: rolsuper=f, rolbypassrls=f, rolcanlogin=t

-- =============================================================================
-- Step 5: Create test tenant schemas (AC5)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS tenant_test_1;
CREATE SCHEMA IF NOT EXISTS tenant_test_2;
CREATE SCHEMA IF NOT EXISTS tenant_test_3;

-- Grant test_user full access to tenant schemas
GRANT ALL ON SCHEMA tenant_test_1 TO test_user;
GRANT ALL ON SCHEMA tenant_test_2 TO test_user;
GRANT ALL ON SCHEMA tenant_test_3 TO test_user;

-- Set default privileges for future tables in tenant schemas
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_test_1 GRANT ALL ON TABLES TO test_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_test_2 GRANT ALL ON TABLES TO test_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_test_3 GRANT ALL ON TABLES TO test_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_test_1 GRANT ALL ON SEQUENCES TO test_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_test_2 GRANT ALL ON SEQUENCES TO test_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_test_3 GRANT ALL ON SEQUENCES TO test_user;

-- =============================================================================
-- Step 6: Create sample tables with RLS (AC5, AC7)
-- These demonstrate the RLS pattern; actual tables are created by migrations
-- =============================================================================

-- Create projects table in each tenant schema
CREATE TABLE IF NOT EXISTS tenant_test_1.projects (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID NOT NULL,
  name        VARCHAR(255) NOT NULL,
  created_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tenant_test_2.projects (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID NOT NULL,
  name        VARCHAR(255) NOT NULL,
  created_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tenant_test_3.projects (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID NOT NULL,
  name        VARCHAR(255) NOT NULL,
  created_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Enable RLS on all tenant tables
ALTER TABLE tenant_test_1.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_test_2.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_test_3.projects ENABLE ROW LEVEL SECURITY;

-- Force RLS for table owner too (CRITICAL: prevents bypass even for table owner)
ALTER TABLE tenant_test_1.projects FORCE ROW LEVEL SECURITY;
ALTER TABLE tenant_test_2.projects FORCE ROW LEVEL SECURITY;
ALTER TABLE tenant_test_3.projects FORCE ROW LEVEL SECURITY;

-- Create RLS policies
DO $$
BEGIN
  -- Drop existing policies if they exist (idempotent)
  DROP POLICY IF EXISTS tenant_isolation ON tenant_test_1.projects;
  DROP POLICY IF EXISTS tenant_isolation ON tenant_test_2.projects;
  DROP POLICY IF EXISTS tenant_isolation ON tenant_test_3.projects;

  CREATE POLICY tenant_isolation ON tenant_test_1.projects
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
  CREATE POLICY tenant_isolation ON tenant_test_2.projects
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
  CREATE POLICY tenant_isolation ON tenant_test_3.projects
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

  RAISE NOTICE 'RLS policies created on all tenant schemas';
END
$$;

-- Grant test_user access to tenant tables
GRANT ALL ON ALL TABLES IN SCHEMA tenant_test_1 TO test_user;
GRANT ALL ON ALL TABLES IN SCHEMA tenant_test_2 TO test_user;
GRANT ALL ON ALL TABLES IN SCHEMA tenant_test_3 TO test_user;

-- =============================================================================
-- Verification complete
-- =============================================================================

\echo '============================================='
\echo 'Test database initialization complete.'
\echo 'qualisys_test database ready'
\echo 'test_user created with NOSUPERUSER, NOBYPASSRLS'
\echo 'Tenant schemas: tenant_test_1, tenant_test_2, tenant_test_3'
\echo 'RLS policies applied and forced'
\echo '============================================='
