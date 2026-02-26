-- Local Development Database Initialization
-- Story: 0-21 Local Development Environment (Podman Compose)
-- AC: 2  - PostgreSQL with pre-created schemas
--
-- Runs automatically on first `podman-compose up` via entrypoint.
-- Creates dev tenant schemas, extensions, base tables, and RLS policies.
-- Separate from init-test-db.sql (Story 0-14) which uses qualisys_test DB.

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- Create development tenant schemas
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS tenant_dev_1;
CREATE SCHEMA IF NOT EXISTS tenant_dev_2;

-- =============================================================================
-- Create base tables in each tenant schema
-- =============================================================================
DO $$
DECLARE
  schema_name TEXT;
BEGIN
  FOR schema_name IN SELECT unnest(ARRAY['tenant_dev_1', 'tenant_dev_2'])
  LOOP
    -- Users table
    EXECUTE format('
      CREATE TABLE IF NOT EXISTS %I.users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID NOT NULL,
        email VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        first_name VARCHAR(255) NOT NULL,
        last_name VARCHAR(255) NOT NULL,
        role VARCHAR(50) NOT NULL DEFAULT ''member'',
        organization_id UUID,
        is_active BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
      )', schema_name);

    -- Organizations table
    EXECUTE format('
      CREATE TABLE IF NOT EXISTS %I.organizations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(100) NOT NULL UNIQUE,
        tenant_id UUID NOT NULL,
        plan VARCHAR(50) NOT NULL DEFAULT ''free'',
        settings JSONB DEFAULT ''{}'',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
      )', schema_name);

    -- Projects table (Story 1.9: added slug, app_url, github_repo_url, status, created_by)
    EXECUTE format('
      CREATE TABLE IF NOT EXISTS %I.projects (
        id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name             VARCHAR(255) NOT NULL,
        description      TEXT,
        organization_id  UUID REFERENCES %I.organizations(id),
        tenant_id        UUID NOT NULL,
        slug             VARCHAR(100) NOT NULL,
        app_url          VARCHAR(500),
        github_repo_url  VARCHAR(500),
        status           VARCHAR(20) NOT NULL DEFAULT ''active'',
        settings         JSONB DEFAULT ''{}'',
        is_active        BOOLEAN NOT NULL DEFAULT true,
        created_by       UUID,
        created_at       TIMESTAMPTZ DEFAULT NOW(),
        updated_at       TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (slug)
      )', schema_name, schema_name);

    -- Test cases table
    EXECUTE format('
      CREATE TABLE IF NOT EXISTS %I.test_cases (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID NOT NULL,
        project_id UUID NOT NULL,
        title VARCHAR(500) NOT NULL,
        description TEXT,
        priority VARCHAR(50) NOT NULL DEFAULT ''medium'',
        status VARCHAR(50) NOT NULL DEFAULT ''active'',
        steps JSONB DEFAULT ''[]'',
        tags TEXT[] DEFAULT ''{}'',
        estimated_duration INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
      )', schema_name);

    -- Test executions table
    EXECUTE format('
      CREATE TABLE IF NOT EXISTS %I.test_executions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID NOT NULL,
        test_case_id UUID NOT NULL,
        status VARCHAR(50) NOT NULL,
        executed_by UUID,
        start_time TIMESTAMPTZ,
        end_time TIMESTAMPTZ,
        duration INTEGER DEFAULT 0,
        environment VARCHAR(100),
        browser VARCHAR(100),
        notes TEXT,
        error_message TEXT,
        screenshots TEXT[] DEFAULT ''{}'',
        created_at TIMESTAMPTZ DEFAULT NOW()
      )', schema_name);

    -- Enable Row Level Security
    EXECUTE format('ALTER TABLE %I.users ENABLE ROW LEVEL SECURITY', schema_name);
    EXECUTE format('ALTER TABLE %I.organizations ENABLE ROW LEVEL SECURITY', schema_name);
    EXECUTE format('ALTER TABLE %I.projects ENABLE ROW LEVEL SECURITY', schema_name);
    EXECUTE format('ALTER TABLE %I.test_cases ENABLE ROW LEVEL SECURITY', schema_name);
    EXECUTE format('ALTER TABLE %I.test_executions ENABLE ROW LEVEL SECURITY', schema_name);

    -- RLS policies: isolate by tenant_id from session variable
    EXECUTE format('
      CREATE POLICY IF NOT EXISTS tenant_isolation ON %I.users
        USING (tenant_id::text = current_setting(''app.current_tenant'', true))
    ', schema_name);
    EXECUTE format('
      CREATE POLICY IF NOT EXISTS tenant_isolation ON %I.organizations
        USING (tenant_id::text = current_setting(''app.current_tenant'', true))
    ', schema_name);
    EXECUTE format('
      CREATE POLICY IF NOT EXISTS tenant_isolation ON %I.projects
        USING (tenant_id::text = current_setting(''app.current_tenant'', true))
    ', schema_name);
    EXECUTE format('
      CREATE POLICY IF NOT EXISTS tenant_isolation ON %I.test_cases
        USING (tenant_id::text = current_setting(''app.current_tenant'', true))
    ', schema_name);
    EXECUTE format('
      CREATE POLICY IF NOT EXISTS tenant_isolation ON %I.test_executions
        USING (tenant_id::text = current_setting(''app.current_tenant'', true))
    ', schema_name);

    RAISE NOTICE 'Schema % initialized with tables and RLS', schema_name;
  END LOOP;
END $$;

-- =============================================================================
-- Public organizations table (tenant registry)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  slug VARCHAR(255) NOT NULL,
  tenant_id UUID NOT NULL UNIQUE,
  schema_name VARCHAR(255) NOT NULL,
  plan VARCHAR(50) NOT NULL DEFAULT 'free',
  settings JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Grant permissions to the application user
-- =============================================================================
GRANT USAGE ON SCHEMA tenant_dev_1, tenant_dev_2 TO qualisys;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA tenant_dev_1 TO qualisys;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA tenant_dev_2 TO qualisys;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO qualisys;

DO $$ BEGIN RAISE NOTICE 'Local development database initialization complete'; END $$;
