-- =============================================================================
-- RLS Isolation Verification Script
-- Story: 0-14 Test Database Provisioning
-- AC: 7  - Isolation verification: tenant_test_1 cannot access tenant_test_2 data
--
-- USAGE:
--   psql $TEST_DATABASE_URL -f infrastructure/scripts/isolation-test.sql
--   npm run db:isolation:test
--
-- PREREQUISITES:
--   - init-test-db.sql has been run
--   - test_user role exists with NOSUPERUSER, NOBYPASSRLS
--   - Tenant schemas with RLS policies exist
--
-- EXPECTED OUTPUT:
--   All assertions pass with NOTICE messages
--   Script exits cleanly (no EXCEPTION raised)
-- =============================================================================

\echo '============================================='
\echo 'RLS ISOLATION VERIFICATION'
\echo '============================================='

-- =============================================================================
-- Test 1: Verify test_user has NO SUPERUSER and NO BYPASSRLS
-- =============================================================================

\echo ''
\echo '[Test 1] Verifying test_user permissions...'

DO $$
DECLARE
  is_super BOOLEAN;
  bypass_rls BOOLEAN;
BEGIN
  SELECT rolsuper, rolbypassrls INTO is_super, bypass_rls
  FROM pg_roles WHERE rolname = 'test_user';

  IF is_super THEN
    RAISE EXCEPTION 'SECURITY VIOLATION: test_user has SUPERUSER privilege!';
  END IF;

  IF bypass_rls THEN
    RAISE EXCEPTION 'SECURITY VIOLATION: test_user has BYPASSRLS privilege!';
  END IF;

  RAISE NOTICE 'PASS: test_user has NOSUPERUSER, NOBYPASSRLS';
END
$$;

-- =============================================================================
-- Test 2: Verify RLS is enabled on tenant tables
-- =============================================================================

\echo ''
\echo '[Test 2] Verifying RLS is enabled on tenant tables...'

DO $$
DECLARE
  rls_enabled BOOLEAN;
BEGIN
  SELECT rowsecurity INTO rls_enabled
  FROM pg_tables
  WHERE schemaname = 'tenant_test_1' AND tablename = 'projects';

  IF NOT rls_enabled THEN
    RAISE EXCEPTION 'RLS NOT ENABLED on tenant_test_1.projects!';
  END IF;

  SELECT rowsecurity INTO rls_enabled
  FROM pg_tables
  WHERE schemaname = 'tenant_test_2' AND tablename = 'projects';

  IF NOT rls_enabled THEN
    RAISE EXCEPTION 'RLS NOT ENABLED on tenant_test_2.projects!';
  END IF;

  RAISE NOTICE 'PASS: RLS enabled on all tenant project tables';
END
$$;

-- =============================================================================
-- Test 3: Verify RLS policies exist
-- =============================================================================

\echo ''
\echo '[Test 3] Verifying RLS policies exist...'

DO $$
DECLARE
  policy_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO policy_count
  FROM pg_policies
  WHERE schemaname = 'tenant_test_1' AND tablename = 'projects';

  IF policy_count = 0 THEN
    RAISE EXCEPTION 'No RLS policies on tenant_test_1.projects!';
  END IF;

  SELECT COUNT(*) INTO policy_count
  FROM pg_policies
  WHERE schemaname = 'tenant_test_2' AND tablename = 'projects';

  IF policy_count = 0 THEN
    RAISE EXCEPTION 'No RLS policies on tenant_test_2.projects!';
  END IF;

  RAISE NOTICE 'PASS: RLS policies exist on all tenant project tables';
END
$$;

-- =============================================================================
-- Test 4: Cross-tenant data isolation
-- Insert data as tenant 1, verify tenant 2 cannot see it
-- =============================================================================

\echo ''
\echo '[Test 4] Testing cross-tenant data isolation...'

-- Clean up any existing test data
TRUNCATE tenant_test_1.projects CASCADE;
TRUNCATE tenant_test_2.projects CASCADE;

-- Begin a transaction for isolation testing
BEGIN;

-- Set context to tenant 1
SET LOCAL app.current_tenant = '11111111-1111-1111-1111-111111111111';

-- Insert data as tenant 1
INSERT INTO tenant_test_1.projects (tenant_id, name)
VALUES ('11111111-1111-1111-1111-111111111111', 'Tenant 1 Secret Project');

-- Verify tenant 1 can see their own data
DO $$
DECLARE
  row_count INTEGER;
BEGIN
  SET LOCAL app.current_tenant = '11111111-1111-1111-1111-111111111111';

  SELECT COUNT(*) INTO row_count
  FROM tenant_test_1.projects
  WHERE name = 'Tenant 1 Secret Project';

  IF row_count != 1 THEN
    RAISE EXCEPTION 'Tenant 1 cannot see their own data! Found % rows', row_count;
  END IF;

  RAISE NOTICE 'PASS: Tenant 1 can see their own data (% row)', row_count;
END
$$;

-- Switch to tenant 2 and verify they CANNOT see tenant 1 data
DO $$
DECLARE
  row_count INTEGER;
BEGIN
  SET LOCAL app.current_tenant = '22222222-2222-2222-2222-222222222222';

  SELECT COUNT(*) INTO row_count
  FROM tenant_test_1.projects;

  IF row_count > 0 THEN
    RAISE EXCEPTION 'RLS VIOLATION: Tenant 2 can see % rows of Tenant 1 data!', row_count;
  END IF;

  RAISE NOTICE 'PASS: Tenant 2 cannot see Tenant 1 data (0 rows visible)';
END
$$;

-- Rollback test data
ROLLBACK;

-- =============================================================================
-- Test 5: Verify tenant 2 data is isolated from tenant 1
-- =============================================================================

\echo ''
\echo '[Test 5] Testing reverse isolation (tenant 2 -> tenant 1)...'

BEGIN;

-- Insert as tenant 2
SET LOCAL app.current_tenant = '22222222-2222-2222-2222-222222222222';
INSERT INTO tenant_test_2.projects (tenant_id, name)
VALUES ('22222222-2222-2222-2222-222222222222', 'Tenant 2 Confidential');

-- Verify tenant 1 cannot see tenant 2 data
DO $$
DECLARE
  row_count INTEGER;
BEGIN
  SET LOCAL app.current_tenant = '11111111-1111-1111-1111-111111111111';

  SELECT COUNT(*) INTO row_count
  FROM tenant_test_2.projects;

  IF row_count > 0 THEN
    RAISE EXCEPTION 'RLS VIOLATION: Tenant 1 can see % rows of Tenant 2 data!', row_count;
  END IF;

  RAISE NOTICE 'PASS: Tenant 1 cannot see Tenant 2 data (0 rows visible)';
END
$$;

ROLLBACK;

-- =============================================================================
-- Test 6: Verify tenant 3 is also isolated
-- =============================================================================

\echo ''
\echo '[Test 6] Testing tenant 3 isolation...'

BEGIN;

SET LOCAL app.current_tenant = '11111111-1111-1111-1111-111111111111';
INSERT INTO tenant_test_3.projects (tenant_id, name)
VALUES ('11111111-1111-1111-1111-111111111111', 'Shared Schema Test');

DO $$
DECLARE
  row_count INTEGER;
BEGIN
  SET LOCAL app.current_tenant = '33333333-3333-3333-3333-333333333333';

  SELECT COUNT(*) INTO row_count
  FROM tenant_test_3.projects;

  IF row_count > 0 THEN
    RAISE EXCEPTION 'RLS VIOLATION: Tenant 3 can see Tenant 1 data in shared schema!';
  END IF;

  RAISE NOTICE 'PASS: Tenant 3 isolation verified';
END
$$;

ROLLBACK;

-- =============================================================================
-- Results Summary
-- =============================================================================

\echo ''
\echo '============================================='
\echo 'ALL ISOLATION TESTS PASSED'
\echo '============================================='
\echo 'Test 1: test_user permissions (NOSUPERUSER, NOBYPASSRLS)'
\echo 'Test 2: RLS enabled on tenant tables'
\echo 'Test 3: RLS policies exist'
\echo 'Test 4: Tenant 1 data invisible to Tenant 2'
\echo 'Test 5: Tenant 2 data invisible to Tenant 1'
\echo 'Test 6: Tenant 3 isolation verified'
\echo '============================================='
