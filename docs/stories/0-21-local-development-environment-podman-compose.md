# Story 0.21: Local Development Environment (Podman Compose)

Status: ready-for-dev

## Story

As a **Developer**,
I want **a local development environment setup**,
so that **I can develop and test locally without cloud dependencies**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | compose.yml file created with all required services | File exists and `podman-compose config` validates |
| AC2 | PostgreSQL service runs with pre-created schemas | Connect to localhost:5432, query tenant schema |
| AC3 | Redis service runs and accepts connections | Connect to localhost:6379, PING returns PONG |
| AC4 | API service runs with hot reload | Change code, verify reload without restart |
| AC5 | Web service runs with hot reload | Change code, verify Next.js fast refresh |
| AC6 | MailCatcher service runs for email testing | Access http://localhost:1080 shows mail UI |
| AC7 | README.md documents complete setup steps | Follow README, environment works |
| AC8 | .env.example template provided with all variables | Copy to .env, all services start |
| AC9 | Seed data script populates local database | Run seed, verify test data exists |
| AC10 | Local setup completes in <30 minutes for new developers | Time setup from clone to running app |
| AC11 | Troubleshooting guide covers common issues | Guide addresses Podman, port conflicts, DB issues |
| AC12 | Health check endpoints accessible | curl localhost:3001/health returns 200 |

## Tasks / Subtasks

- [ ] **Task 1: Podman Compose Configuration** (AC: 1, 2, 3, 6)
  - [ ] 1.1 Create compose.yml with service definitions
  - [ ] 1.2 Configure PostgreSQL service with init scripts
  - [ ] 1.3 Configure Redis service
  - [ ] 1.4 Configure MailCatcher service
  - [ ] 1.5 Set up Podman network for service communication
  - [ ] 1.6 Add health checks for all services
  - [ ] 1.7 Verify all services start with `podman-compose up`

- [ ] **Task 2: Application Services Setup** (AC: 4, 5, 12)
  - [ ] 2.1 Create API service Containerfile.dev for development
  - [ ] 2.2 Configure volume mounts for hot reload
  - [ ] 2.3 Set up nodemon/ts-node-dev for API hot reload
  - [ ] 2.4 Create Web service configuration for Next.js
  - [ ] 2.5 Configure health check endpoints
  - [ ] 2.6 Test hot reload functionality

- [ ] **Task 3: Database Initialization** (AC: 2, 9)
  - [ ] 3.1 Create PostgreSQL init script (create schemas)
  - [ ] 3.2 Create migration runner script
  - [ ] 3.3 Create seed data script
  - [ ] 3.4 Configure seed script in npm/package.json
  - [ ] 3.5 Verify multi-tenant schemas created on startup

- [ ] **Task 4: Environment Configuration** (AC: 8)
  - [ ] 4.1 Create .env.example with all required variables
  - [ ] 4.2 Document each environment variable
  - [ ] 4.3 Add .env to .gitignore
  - [ ] 4.4 Create environment validation script
  - [ ] 4.5 Test setup with fresh .env copy

- [ ] **Task 5: Documentation** (AC: 7, 10, 11)
  - [ ] 5.1 Write README.md with setup instructions
  - [ ] 5.2 Document prerequisites (Podman, Node.js versions)
  - [ ] 5.3 Create step-by-step quick start guide
  - [ ] 5.4 Write troubleshooting guide
  - [ ] 5.5 Add architecture diagram for local services
  - [ ] 5.6 Time and validate <30 minute setup

- [ ] **Task 6: Validation and Testing** (AC: All)
  - [ ] 6.1 Test complete setup on clean machine
  - [ ] 6.2 Verify all services communicate correctly
  - [ ] 6.3 Test email sending via MailCatcher
  - [ ] 6.4 Verify hot reload for API and Web
  - [ ] 6.5 Run integration tests against local environment

## Dev Notes

### Architecture Alignment

This story enables developer productivity per architecture requirements:

- **Local-first development**: No cloud dependencies for day-to-day coding
- **Parity with production**: Same services (PostgreSQL, Redis) as production
- **Fast iteration**: Hot reload for immediate feedback
- **10Pearls Compliance**: Uses Podman (approved container runtime)

### Technical Constraints

- **Podman 4.x+**: Rootless, daemonless, OCI-compliant container runtime
- **Podman Compose**: Compatible with compose.yml format
- **PostgreSQL 15+**: Match production version
- **Redis 7+**: Match production version
- **Node.js 18+**: LTS version for API and Web services
- **Volume mounts**: Source code mounted for hot reload

### Podman Compose Configuration

```yaml
# compose.yml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: qualisys-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-qualisys}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-qualisys_dev}
      POSTGRES_DB: ${POSTGRES_DB:-qualisys_master}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/01-init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U qualisys -d qualisys_master"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis Cache
  redis:
    image: redis:7-alpine
    container_name: qualisys-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # MailCatcher for email testing
  mailcatcher:
    image: schickling/mailcatcher
    container_name: qualisys-mailcatcher
    ports:
      - "1080:1080"  # Web UI
      - "1025:1025"  # SMTP
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:1080"]
      interval: 10s
      timeout: 5s
      retries: 5

  # API Service (Development)
  api:
    build:
      context: ./api
      dockerfile: Containerfile.dev
    container_name: qualisys-api
    environment:
      NODE_ENV: development
      DATABASE_URL: postgresql://${POSTGRES_USER:-qualisys}:${POSTGRES_PASSWORD:-qualisys_dev}@postgres:5432/${POSTGRES_DB:-qualisys_master}
      REDIS_URL: redis://redis:6379
      SMTP_HOST: mailcatcher
      SMTP_PORT: 1025
      JWT_SECRET: ${JWT_SECRET:-dev_jwt_secret_change_in_production}
      PORT: 3001
    ports:
      - "3001:3001"
    volumes:
      - ./api/src:/app/src:Z
      - ./api/package.json:/app/package.json:Z
      - api_node_modules:/app/node_modules
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # Web Service (Development)
  web:
    build:
      context: ./web
      dockerfile: Containerfile.dev
    container_name: qualisys-web
    environment:
      NODE_ENV: development
      NEXT_PUBLIC_API_URL: http://localhost:3001
      WATCHPACK_POLLING: true
    ports:
      - "3000:3000"
    volumes:
      - ./web/src:/app/src:Z
      - ./web/public:/app/public:Z
      - ./web/package.json:/app/package.json:Z
      - web_node_modules:/app/node_modules
      - web_next:/app/.next
    depends_on:
      api:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

volumes:
  postgres_data:
  redis_data:
  api_node_modules:
  web_node_modules:
  web_next:

networks:
  default:
    name: qualisys-network
```

**Note**: The `:Z` suffix on volume mounts is for SELinux relabeling (required on Fedora/RHEL systems). Remove if not using SELinux.

### API Containerfile.dev

```dockerfile
# api/Containerfile.dev
FROM node:18-alpine

WORKDIR /app

# Install dependencies first (cached layer)
COPY package*.json ./
RUN npm ci

# Install development tools
RUN npm install -g ts-node-dev

# Copy source (will be overwritten by volume mount)
COPY . .

# Expose port
EXPOSE 3001

# Development command with hot reload
CMD ["npx", "ts-node-dev", "--respawn", "--transpile-only", "src/index.ts"]
```

### Web Containerfile.dev

```dockerfile
# web/Containerfile.dev
FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source (will be overwritten by volume mount)
COPY . .

# Expose port
EXPOSE 3000

# Development command with hot reload
CMD ["npm", "run", "dev"]
```

### Database Initialization Script

```sql
-- scripts/init-db.sql
-- Initialize QUALISYS development database

-- Create test tenant schemas
CREATE SCHEMA IF NOT EXISTS tenant_dev_1;
CREATE SCHEMA IF NOT EXISTS tenant_dev_2;
CREATE SCHEMA IF NOT EXISTS tenant_test;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create base tables in each tenant schema
DO $$
DECLARE
  schema_name TEXT;
BEGIN
  FOR schema_name IN SELECT unnest(ARRAY['tenant_dev_1', 'tenant_dev_2', 'tenant_test'])
  LOOP
    EXECUTE format('
      CREATE TABLE IF NOT EXISTS %I.users (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        name VARCHAR(255),
        role VARCHAR(50) DEFAULT ''member'',
        tenant_id UUID NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
      )', schema_name);

    EXECUTE format('
      CREATE TABLE IF NOT EXISTS %I.organizations (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(100) UNIQUE NOT NULL,
        tenant_id UUID NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
      )', schema_name);

    EXECUTE format('
      CREATE TABLE IF NOT EXISTS %I.projects (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        name VARCHAR(255) NOT NULL,
        description TEXT,
        organization_id UUID REFERENCES %I.organizations(id),
        tenant_id UUID NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
      )', schema_name, schema_name);

    -- Enable RLS
    EXECUTE format('ALTER TABLE %I.users ENABLE ROW LEVEL SECURITY', schema_name);
    EXECUTE format('ALTER TABLE %I.organizations ENABLE ROW LEVEL SECURITY', schema_name);
    EXECUTE format('ALTER TABLE %I.projects ENABLE ROW LEVEL SECURITY', schema_name);
  END LOOP;
END $$;

-- Grant permissions to app user
GRANT USAGE ON SCHEMA tenant_dev_1, tenant_dev_2, tenant_test TO qualisys;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA tenant_dev_1 TO qualisys;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA tenant_dev_2 TO qualisys;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA tenant_test TO qualisys;

-- Output confirmation
DO $$ BEGIN RAISE NOTICE 'Database initialization complete'; END $$;
```

### Seed Data Script

```typescript
// scripts/seed.ts
import { Pool } from 'pg';
import { faker } from '@faker-js/faker';
import * as bcrypt from 'bcrypt';

const pool = new Pool({
  connectionString: process.env.DATABASE_URL ||
    'postgresql://qualisys:qualisys_dev@localhost:5432/qualisys_master',
});

async function seed() {
  console.log('Seeding database...');

  const schemas = ['tenant_dev_1', 'tenant_dev_2'];

  for (const schema of schemas) {
    const tenantId = faker.string.uuid();

    // Create organization
    const orgResult = await pool.query(`
      INSERT INTO ${schema}.organizations (id, name, slug, tenant_id)
      VALUES ($1, $2, $3, $4)
      RETURNING id
    `, [faker.string.uuid(), faker.company.name(), faker.helpers.slugify(faker.company.name().toLowerCase()), tenantId]);

    const orgId = orgResult.rows[0].id;

    // Create admin user
    const passwordHash = await bcrypt.hash('password123', 10);
    await pool.query(`
      INSERT INTO ${schema}.users (email, password_hash, name, role, tenant_id)
      VALUES ($1, $2, $3, $4, $5)
    `, [`admin@${schema}.test`, passwordHash, 'Admin User', 'admin', tenantId]);

    // Create test users
    for (let i = 0; i < 5; i++) {
      await pool.query(`
        INSERT INTO ${schema}.users (email, password_hash, name, role, tenant_id)
        VALUES ($1, $2, $3, $4, $5)
      `, [
        faker.internet.email(),
        passwordHash,
        faker.person.fullName(),
        faker.helpers.arrayElement(['member', 'viewer']),
        tenantId,
      ]);
    }

    // Create projects
    for (let i = 0; i < 3; i++) {
      await pool.query(`
        INSERT INTO ${schema}.projects (name, description, organization_id, tenant_id)
        VALUES ($1, $2, $3, $4)
      `, [
        faker.commerce.productName(),
        faker.lorem.paragraph(),
        orgId,
        tenantId,
      ]);
    }

    console.log(`  Seeded ${schema}`);
  }

  console.log('Seed complete!');
  console.log('\nTest credentials:');
  console.log('  Email: admin@tenant_dev_1.test');
  console.log('  Password: password123');

  await pool.end();
}

seed().catch((err) => {
  console.error('Seed error:', err);
  process.exit(1);
});
```

### Environment Template

```bash
# .env.example
# Copy this file to .env and update values as needed

# Database
POSTGRES_USER=qualisys
POSTGRES_PASSWORD=qualisys_dev
POSTGRES_DB=qualisys_master
DATABASE_URL=postgresql://qualisys:qualisys_dev@localhost:5432/qualisys_master

# Redis
REDIS_URL=redis://localhost:6379

# API
JWT_SECRET=dev_jwt_secret_change_in_production
PORT=3001

# Email (MailCatcher)
SMTP_HOST=localhost
SMTP_PORT=1025

# Web
NEXT_PUBLIC_API_URL=http://localhost:3001

# Optional: LLM API keys (for Epic 2+ development)
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
```

### README Setup Instructions

```markdown
# QUALISYS Local Development Setup

## Prerequisites

- **Podman Desktop 1.x+** ([Download](https://podman-desktop.io/)) - 10Pearls approved
  - OR Podman CLI 4.x+ (`winget install RedHat.Podman` on Windows)
- **podman-compose** (`pip install podman-compose` or included with Podman Desktop)
- Node.js 18+ (optional, for running scripts outside containers)
- Git

**Note**: Docker Desktop is NOT approved for 10Pearls systems per company policy.

## Quick Start (< 30 minutes)

### 1. Clone Repository
```bash
git clone https://github.com/qualisys/qualisys.git
cd qualisys
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env if needed (defaults work for local dev)
```

### 3. Initialize Podman Machine (Windows/macOS only)
```bash
podman machine init
podman machine start
```

### 4. Start Services
```bash
podman-compose up -d
```

### 5. Run Database Migrations
```bash
podman-compose exec api npm run migrate
```

### 6. Seed Test Data
```bash
podman-compose exec api npm run seed
```

### 7. Access Application
- **Web App**: http://localhost:3000
- **API**: http://localhost:3001
- **API Health**: http://localhost:3001/health
- **MailCatcher**: http://localhost:1080

### Test Credentials
- Email: `admin@tenant_dev_1.test`
- Password: `password123`

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Web | http://localhost:3000 | Next.js frontend |
| API | http://localhost:3001 | FastAPI/Express backend |
| PostgreSQL | localhost:5432 | Database |
| Redis | localhost:6379 | Cache |
| MailCatcher | http://localhost:1080 | Email testing UI |

## Common Commands

```bash
# Start all services
podman-compose up -d

# View logs
podman-compose logs -f

# View specific service logs
podman-compose logs -f api

# Stop all services
podman-compose down

# Stop and remove volumes (reset database)
podman-compose down -v

# Rebuild services after Containerfile changes
podman-compose up -d --build

# Run tests
podman-compose exec api npm test

# Access PostgreSQL CLI
podman-compose exec postgres psql -U qualisys -d qualisys_master

# Access Redis CLI
podman-compose exec redis redis-cli
```

## Hot Reload

Both API and Web services have hot reload enabled:

- **API**: Uses `ts-node-dev` - changes to `api/src/**` trigger restart
- **Web**: Uses Next.js Fast Refresh - changes appear instantly

## Troubleshooting

### Port Conflicts
If you see "port already in use" errors:
```bash
# Check what's using the port
lsof -i :3000  # or :3001, :5432, :6379

# Stop the conflicting service or change ports in compose.yml
```

### Podman Machine Issues (Windows/macOS)
```bash
# Check machine status
podman machine list

# Restart machine
podman machine stop
podman machine start

# Reset machine (if persistent issues)
podman machine rm
podman machine init
podman machine start
```

### Container Issues
```bash
# Reset Podman environment
podman-compose down -v
podman system prune -f
podman-compose up -d --build
```

### Database Connection Issues
```bash
# Check PostgreSQL is healthy
podman-compose ps

# View PostgreSQL logs
podman-compose logs postgres

# Reset database
podman-compose down -v
podman-compose up -d
podman-compose exec api npm run migrate
podman-compose exec api npm run seed
```

### SELinux Issues (Fedora/RHEL)
If you see permission denied errors on volume mounts:
- The compose.yml uses `:Z` suffix for SELinux relabeling
- Alternatively, run `sudo setsebool -P container_manage_cgroup true`

### Hot Reload Not Working
On Windows, ensure Podman machine has sufficient resources:
- Podman Desktop -> Settings -> Resources -> Podman Machine
- Allocate at least 4GB RAM

For WSL2 users, ensure project is in WSL filesystem (not /mnt/c/).
```

### Project Structure Notes

```
/
├── compose.yml                  # Main compose file
├── .env.example                 # Environment template
├── .env                         # Local environment (gitignored)
├── scripts/
│   ├── init-db.sql             # PostgreSQL initialization
│   └── seed.ts                 # Test data seeding
├── api/
│   ├── Containerfile.dev       # Development Containerfile
│   ├── src/                    # Source code (mounted)
│   └── package.json
├── web/
│   ├── Containerfile.dev       # Development Containerfile
│   ├── src/                    # Source code (mounted)
│   └── package.json
└── docs/
    └── local-development.md    # Extended documentation
```

### Dependencies

- **None** - This story has no dependencies and can start Day 1
- Outputs used by:
  - Epic 1-5: All feature development uses local environment
  - Story 0.10: Local tests run against this environment

### Security Considerations

1. **Threat: Secrets in compose.yml** -> Use .env file (gitignored)
2. **Threat: Production secrets in dev** -> Different secrets for local
3. **Threat: Dev data in production** -> Clear separation of environments
4. **Threat: Port exposure** -> Bind to localhost only in production
5. **Podman rootless mode** -> Enhanced security vs Docker daemon

### Performance Tips

- Use named volumes for `node_modules` to avoid host filesystem slowness
- Podman is daemonless - no background process consuming resources
- Allocate sufficient resources to Podman machine (4GB+ RAM recommended)
- On Windows/macOS, Podman machine runs a lightweight Linux VM

### Why Podman?

Per 10Pearls company policy (January 2026):
- Docker Desktop is NOT approved for 10Pearls systems
- Podman is the approved container runtime
- Key benefits: rootless by default, daemonless, OCI-compliant
- Same Containerfile/compose.yml format - compatible with existing knowledge

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#Development-Environment]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.21]
- [Podman Documentation](https://docs.podman.io/)
- [Podman Desktop](https://podman-desktop.io/)
- [Podman Compose](https://github.com/containers/podman-compose)
- [Next.js Deployment](https://nextjs.org/docs/deployment)

## Dev Agent Record

### Context Reference

- [docs/stories/0-21-local-development-environment-podman-compose.context.xml](./0-21-local-development-environment-podman-compose.context.xml)

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

### File List

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-01-24 | SM Agent (Bob) | Story drafted from Epic 0 tech spec and epic file |
| 2026-01-24 | PM Agent (John) | Migrated from Docker to Podman per 10Pearls company policy |
