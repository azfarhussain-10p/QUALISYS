-- =============================================================================
-- Database Initialization Script
-- Story: 0-4 PostgreSQL Multi-Tenant Database
-- AC: 7  - Master database (qualisys_master) — created by Terraform db_name param
-- AC: 8  - app_user with NO SUPERUSER, NO BYPASSRLS
-- AC: 10 - RLS capability verified
--
-- USAGE:
--   1. Retrieve master credentials from Secrets Manager:
--      aws secretsmanager get-secret-value \
--        --secret-id qualisys/database/master \
--        --query 'SecretString' --output text | jq -r '.password'
--
--   2. Retrieve app_user password from Secrets Manager:
--      aws secretsmanager get-secret-value \
--        --secret-id qualisys/database/connection \
--        --query 'SecretString' --output text | jq -r '.password'
--
--   3. Connect as master user and run this script:
--      PGPASSWORD=<master_password> psql \
--        -h <rds_endpoint> -U qualisys_admin -d qualisys_master \
--        -v app_user_password="'<app_user_password>'" \
--        -f db-init.sql
--
-- CRITICAL SECURITY CONSTRAINTS:
--   - app_user must NOT have SUPERUSER privileges
--   - app_user must NOT have BYPASSRLS privileges
--   - These constraints are Red Team requirements (Story 0.1)
-- =============================================================================

-- =============================================================================
-- Task 5.3: Create app_user role (AC8)
-- LOGIN: can connect to the database
-- NOSUPERUSER: CRITICAL — cannot bypass security restrictions
-- NOBYPASSRLS: CRITICAL — cannot bypass Row-Level Security policies
-- NOCREATEDB: cannot create new databases
-- NOCREATEROLE: cannot create new roles
-- =============================================================================

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
    CREATE ROLE app_user WITH
      LOGIN
      NOSUPERUSER
      NOBYPASSRLS
      NOCREATEDB
      NOCREATEROLE
      PASSWORD :app_user_password;
    RAISE NOTICE 'Created role: app_user';
  ELSE
    RAISE NOTICE 'Role app_user already exists, updating password';
    ALTER ROLE app_user WITH PASSWORD :app_user_password;
  END IF;
END
$$;

-- =============================================================================
-- Task 5.4: Grant app_user CREATE privilege on qualisys_master (AC8)
-- This allows Epic 1 to create tenant schemas (CREATE SCHEMA tenant_xxx)
-- =============================================================================

GRANT CREATE ON DATABASE qualisys_master TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;

-- =============================================================================
-- Task 5.5: Verify app_user permissions (AC8)
-- Expected output: rolsuper=f, rolbypassrls=f
-- =============================================================================

SELECT
  rolname,
  rolsuper,
  rolbypassrls,
  rolcreatedb,
  rolcreaterole,
  rolcanlogin
FROM pg_roles
WHERE rolname = 'app_user';

-- =============================================================================
-- Task 5.6: Test RLS capability (AC10)
-- Creates a test table, enables RLS, creates a policy, verifies, then cleans up
-- =============================================================================

-- Create a test schema and table
CREATE SCHEMA IF NOT EXISTS rls_test;

CREATE TABLE IF NOT EXISTS rls_test.test_table (
  id          SERIAL PRIMARY KEY,
  tenant_id   UUID NOT NULL,
  data        TEXT
);

-- Enable Row-Level Security
ALTER TABLE rls_test.test_table ENABLE ROW LEVEL SECURITY;

-- Create an RLS policy matching the production pattern
CREATE POLICY tenant_isolation ON rls_test.test_table
  USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Grant access to app_user for the test
GRANT USAGE ON SCHEMA rls_test TO app_user;
GRANT SELECT, INSERT ON rls_test.test_table TO app_user;

-- Verify RLS is enabled
SELECT
  schemaname,
  tablename,
  rowsecurity
FROM pg_tables
WHERE schemaname = 'rls_test' AND tablename = 'test_table';

-- Verify policy exists
SELECT
  policyname,
  tablename,
  cmd,
  qual
FROM pg_policies
WHERE schemaname = 'rls_test' AND tablename = 'test_table';

-- Clean up test resources
DROP POLICY IF EXISTS tenant_isolation ON rls_test.test_table;
DROP TABLE IF EXISTS rls_test.test_table;
DROP SCHEMA IF EXISTS rls_test;

-- Revoke test grants (schema already dropped)
-- No explicit revoke needed since the schema is dropped

-- =============================================================================
-- Verification complete
-- =============================================================================

\echo '============================================='
\echo 'Database initialization complete.'
\echo 'app_user created with NOSUPERUSER, NOBYPASSRLS'
\echo 'RLS capability verified and test artifacts cleaned up'
\echo '============================================='
