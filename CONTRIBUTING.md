# Contributing to QUALISYS

## Development Workflow

### Branch Strategy

- **`main`** — Protected branch. All merges require passing tests and PR review.
- Feature branches — Create from `main`, name as `feature/<short-description>` or `fix/<short-description>`.

### Pull Request Process

1. Create a feature branch from `main`.
2. Make your changes and commit.
3. Push to remote and open a Pull Request against `main`.
4. PR checks run automatically (see below).
5. Address review feedback.
6. Merge when all checks pass and reviewers approve.

## Testing

### Test Pyramid

```
        /\
       /  \      E2E Tests (critical paths only on PR)
      /----\     - Login flow, core user journeys
     /      \    - Full suite runs nightly
    /--------\
   /          \  Integration Tests
  /  API Tests \  - Database operations
 /--------------\ - Service interactions
/                \
/==================\ Unit Tests (80% coverage target)
   Business Logic    - Pure functions, utilities
   Components        - React components
   Validators        - Input validation logic
```

### Running Tests Locally

```bash
# Unit tests (all services)
npm test

# Unit tests with coverage
npm test -- --coverage

# API integration tests (requires PostgreSQL)
npm run test:integration

# E2E critical path tests (requires running app)
npm run test:e2e:critical

# E2E full suite
npm run test:e2e

# Single test file
npx jest path/to/test.test.ts

# Playwright specific browser
npx playwright test --project=chromium-critical
```

### Test Directory Structure

```
api/
├── __tests__/
│   ├── unit/           # API unit tests
│   └── integration/    # API integration tests (needs DB)
web/
├── __tests__/
│   └── unit/           # React component tests
e2e/
├── tests/
│   ├── critical/       # Critical path E2E (run on every PR)
│   └── full/           # Full E2E suite (nightly)
└── playwright.config.ts
```

### Coverage Requirements

| Metric | Threshold |
|--------|-----------|
| Line coverage | 80% |
| Function coverage | 80% |
| Statement coverage | 80% |
| Branch coverage | 70% |

PRs that drop coverage below these thresholds will fail the unit-tests check.

### Flaky Test Policy

Tests are retried automatically in CI before being marked as failed:

| Framework | Retries | Configuration |
|-----------|---------|---------------|
| Jest | 3 | `jest.config.js` — `retryTimes: 3` |
| Playwright | 2 | `playwright.config.ts` — `retries: 2` |

If a test consistently requires retries to pass:

1. Open an issue tagged `flaky-test`.
2. Add the test file path and failure frequency.
3. Investigate root cause (timing, external dependency, shared state).
4. Fix the underlying issue rather than increasing retries.

### Writing Tests

**Unit tests** should:
- Test a single function or component in isolation.
- Mock external dependencies (database, APIs, file system).
- Run without any infrastructure (no DB, no Redis).
- Complete in <1 second per test.

**Integration tests** should:
- Test API endpoints with a real database (PostgreSQL service container).
- Run database migrations before tests.
- Clean up test data after each test suite.
- Use test data factories (see `test/factories/`).

**E2E tests** should:
- Test complete user journeys through the UI.
- Use the `critical/` directory for must-pass flows (login, core features).
- Use the `full/` directory for comprehensive coverage.
- Capture screenshots and videos on failure.

## Deployment

### Staging (Automatic)

Merging to `main` triggers automatic deployment to staging:

1. **Build** — API and Web Docker images are built in parallel, tagged with the Git SHA, and pushed to the container registry (ECR or ACR depending on cloud provider).
2. **Deploy** — Kubernetes deployments in the `staging` namespace are updated with the new image tag via `kubectl set image`. Rolling updates ensure zero downtime (`maxUnavailable: 0`).
3. **Health Check** — Kubernetes readiness and liveness probes verify the new pods are healthy. Failed probes trigger automatic rollback to the previous version.
4. **Notify** — A Slack notification is sent with the deployment result, commit SHA, and staging URL.

**Staging URL:** https://staging.qualisys.dev

**Deployment time target:** <2 minutes from merge to running pods.

**Manifests location:** `infrastructure/kubernetes/staging/`

```
infrastructure/kubernetes/staging/
├── deployment.yaml    # API + Web deployments with rolling updates and probes
├── service.yaml       # ClusterIP services
└── ingress.yaml       # NGINX ingress with SSL (cert-manager)
```

### Production (Manual Approval + Canary Rollout)

Production deployments require manual trigger and approval before proceeding:

1. **Trigger** — A team member manually triggers the production workflow via GitHub Actions with the image tag (Git SHA) from a successful staging deployment.
2. **Approval** — The workflow pauses at the "Approval Gate" job. The GitHub Environment "production" requires approval from DevOps Lead and Tech Lead before deployment proceeds.
3. **Canary (10%)** — The new version is deployed to canary pods (1 of 10 replicas). Smoke tests verify health, readiness, login page, and API authentication. A 2-minute observation period follows.
4. **Rollout (50%)** — Canary scales to 5 replicas (50/50 split). Smoke tests run again.
5. **Rollout (100%)** — Stable deployments are updated to the new version. Canary scales back to 1 replica. Final smoke tests confirm full rollout.
6. **Notify** — A Slack notification is sent with the deployment result, image tag, and production URL.

**Emergency hotfix:** Use `skip_canary: true` to bypass the canary phase and deploy directly via the reusable deploy workflow.

**Production URL:** https://app.qualisys.io

**Deployment time target:** <10 minutes from trigger to full rollout (including smoke tests).

**Triggering a production deployment:**

```bash
# 1. Find the image tag from the latest staging deployment
gh run list --workflow=deploy-staging.yml --limit=5

# 2. Trigger production deployment
gh workflow run deploy-production.yml -f image_tag=<git-sha>

# 3. Approve in GitHub UI when prompted (production environment protection)

# 4. Monitor deployment
gh run watch
```

**Manifests location:** `infrastructure/kubernetes/production/`

```
infrastructure/kubernetes/production/
├── stable-deployment.yaml  # Stable API + Web deployments (9 replicas each)
├── canary-deployment.yaml  # Canary API + Web deployments (1 replica each)
├── service.yaml            # ClusterIP services (traffic splitting via replica ratio)
└── ingress.yaml            # NGINX ingress with SSL (cert-manager) for app.qualisys.io
```

**GitHub Environment Configuration (post-apply):**

```bash
# Create production environment with required reviewers
gh api repos/{owner}/{repo}/environments/production -X PUT \
  -f 'reviewers[][type]=User' \
  -f 'reviewers[][id]=<devops_lead_user_id>' \
  -f 'reviewers[][type]=User' \
  -f 'reviewers[][id]=<tech_lead_user_id>' \
  -F 'wait_timer=5'
```

### Rollback

#### Automatic Rollback

Kubernetes automatically rolls back when:
- Readiness probes fail 3 consecutive times
- Liveness probes fail 3 consecutive times
- Smoke tests fail during canary or rollout phases (workflow job fails, deployment stops)

#### Manual Rollback — Staging

```bash
kubectl rollout undo deployment/qualisys-api -n staging
kubectl rollout undo deployment/qualisys-web -n staging
kubectl rollout history deployment/qualisys-api -n staging
```

#### Manual Rollback — Production

**Option 1: Undo last deployment (revert to previous version)**

```bash
kubectl rollout undo deployment/qualisys-api-stable -n production
kubectl rollout undo deployment/qualisys-web-stable -n production
```

**Option 2: Deploy a specific version**

```bash
# Replace <CONTAINER_REGISTRY> and <PREVIOUS_SHA> with actual values
kubectl set image deployment/qualisys-api-stable \
  qualisys-api=<CONTAINER_REGISTRY>/qualisys-api:<PREVIOUS_SHA> \
  -n production
kubectl set image deployment/qualisys-web-stable \
  qualisys-web=<CONTAINER_REGISTRY>/qualisys-web:<PREVIOUS_SHA> \
  -n production
```

**Option 3: Scale down canary during failed rollout**

```bash
# If canary is causing issues during rollout, scale it to 0
kubectl scale deployment/qualisys-api-canary --replicas=0 -n production
kubectl scale deployment/qualisys-web-canary --replicas=0 -n production

# Restore stable to full replicas
kubectl scale deployment/qualisys-api-stable --replicas=9 -n production
kubectl scale deployment/qualisys-web-stable --replicas=9 -n production
```

**Verify rollback:**

```bash
kubectl rollout status deployment/qualisys-api-stable -n production
kubectl get pods -n production -l app=qualisys-api
kubectl rollout history deployment/qualisys-api-stable -n production
```

**Rollback SLA:** <2 minutes from decision to rolled-back pods.

### Pre-Deployment Checklist

- [ ] Changes tested in staging environment
- [ ] Staging smoke tests passing
- [ ] Database migrations applied to staging (if any)
- [ ] No blocking incidents in progress
- [ ] On-call engineer notified

### Post-Deployment Checklist

- [ ] Smoke tests passing
- [ ] Error rate normal in monitoring
- [ ] No customer-reported issues (15 min observation)
- [ ] Deployment documented in changelog

## CI/CD Pipeline

### PR Checks (Automated)

When you open a PR against `main`, these checks run automatically:

| Check | What it does | Must pass to merge |
|-------|--------------|--------------------|
| **Lint** | ESLint + Ruff | Yes |
| **Format Check** | Prettier + Black | Yes |
| **Type Check** | TypeScript + mypy | Yes |
| **Unit Tests** | Jest (Node 18 + 20 matrix) | Yes |
| **Integration Tests** | API tests with PostgreSQL | Yes |
| **E2E Tests** | Playwright critical paths | Yes |

### Test Results

- Test results appear as PR check annotations.
- A summary comment is posted on the PR with pass/fail counts and coverage.
- Coverage is tracked on [Codecov](https://codecov.io).
- Failed tests show stack traces in the PR comment.

### Branch Protection

The `main` branch requires:
- All status checks passing (unit-tests, integration-tests, e2e-tests).
- Branch is up to date with `main`.
- At least one approving review.
- CODEOWNERS approval for workflow file changes.

## Ingress & Load Balancer Configuration

### Architecture Overview

External traffic flows through the following path:

```
User → DNS (Route 53 / Azure DNS) → Load Balancer (NLB / Azure LB) → NGINX Ingress Controller → Kubernetes Services → Pods
```

### Components

| Component | Namespace | Purpose | Helm Chart |
|-----------|-----------|---------|------------|
| NGINX Ingress Controller | `ingress-nginx` | L7 routing, SSL termination, rate limiting | `ingress-nginx/ingress-nginx` |
| cert-manager | `cert-manager` | Automatic SSL certificate provisioning via Let's Encrypt | `jetstack/cert-manager` |
| Custom Error Pages | `ingress-nginx` | Branded 502/503/504 error pages | ConfigMap |

### Domains

| Domain | Environment | Routes To |
|--------|-------------|-----------|
| `app.qualisys.io` | Production | `qualisys-web-stable:3000` |
| `api.qualisys.io` | Production | `qualisys-api-stable:3000` |
| `staging.qualisys.dev` | Staging | `/api` → `qualisys-api:3000`, `/` → `qualisys-web:3000` |

### Installation

```bash
# 1. Install NGINX Ingress Controller
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  -f infrastructure/kubernetes/ingress-nginx/values.yaml

# 2. Install cert-manager
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  -f infrastructure/kubernetes/cert-manager/values.yaml

# 3. Create Let's Encrypt ClusterIssuers
kubectl apply -f infrastructure/kubernetes/cert-manager/cluster-issuer.yaml

# 4. Apply custom error pages
kubectl apply -f infrastructure/kubernetes/ingress-nginx/custom-error-pages.yaml

# 5. Apply ingress resources
kubectl apply -f infrastructure/kubernetes/staging/ingress.yaml
kubectl apply -f infrastructure/kubernetes/production/ingress.yaml

# 6. Apply DNS records (Terraform)
cd infrastructure/terraform/aws   # or azure
terraform apply -var-file="environments/dev.tfvars"
```

### Ingress Annotations Reference

| Annotation | Value | Purpose |
|-----------|-------|---------|
| `cert-manager.io/cluster-issuer` | `letsencrypt-prod` | SSL certificate provisioning |
| `nginx.ingress.kubernetes.io/ssl-redirect` | `"true"` | Force HTTPS redirect |
| `nginx.ingress.kubernetes.io/force-ssl-redirect` | `"true"` | Force SSL for all requests |
| `nginx.ingress.kubernetes.io/limit-rps` | `"17"` | Rate limit: ~1000 req/min per IP |
| `nginx.ingress.kubernetes.io/limit-burst-multiplier` | `"5"` | Burst allowance multiplier |
| `nginx.ingress.kubernetes.io/limit-connections` | `"10"` | Max concurrent connections per IP |
| `nginx.ingress.kubernetes.io/proxy-body-size` | `"50m"` | Max upload size |
| `nginx.ingress.kubernetes.io/proxy-read-timeout` | `"60"` | Backend read timeout (seconds) |
| `nginx.ingress.kubernetes.io/proxy-send-timeout` | `"60"` | Backend send timeout (seconds) |

### Security Headers

All ingress resources include these security headers via `configuration-snippet`:

| Header | Value | Purpose |
|--------|-------|---------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | HSTS enforcement |
| `X-Frame-Options` | `SAMEORIGIN` | Prevent clickjacking |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-XSS-Protection` | `1; mode=block` | XSS filter |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer info |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Restrict browser APIs |

### SSL Certificates

Certificates are automatically provisioned and renewed by cert-manager:

```bash
# Check certificate status
kubectl get certificates -A
kubectl describe certificate <name> -n <namespace>

# Check ClusterIssuer status
kubectl get clusterissuers
kubectl describe clusterissuer letsencrypt-prod

# Verify SSL from command line
openssl s_client -connect app.qualisys.io:443 -servername app.qualisys.io
```

### Rate Limiting

Rate limiting is set to **1000 requests/minute per IP** (~17 rps):

```bash
# Test rate limiting with hey (HTTP load generator)
hey -n 2000 -c 50 -q 50 https://api.qualisys.io/health

# Expected: After ~1000 requests/min from same IP, HTTP 429 Too Many Requests
```

### DDoS Protection

| Cloud | Protection | Level | Configuration |
|-------|-----------|-------|---------------|
| AWS | Shield Standard | Automatic | Enabled by default for all NLBs — no action needed |
| Azure | DDoS Protection Basic | Automatic | Enabled by default for all public IPs |
| Azure | DDoS Protection Standard | Optional | Enable via Azure Portal for enhanced protection |

### Troubleshooting

**Ingress controller not running:**
```bash
kubectl get pods -n ingress-nginx
kubectl describe pod -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx
```

**SSL certificate not issued:**
```bash
kubectl get certificates -A
kubectl describe certificate <name> -n <namespace>
kubectl get challenges -A  # Check ACME challenges
kubectl logs -n cert-manager -l app=cert-manager
```

**502/503 errors:**
1. Check backend pods are running: `kubectl get pods -n <namespace>`
2. Check service endpoints: `kubectl get endpoints <service> -n <namespace>`
3. Check ingress backend status: `kubectl describe ingress <name> -n <namespace>`
4. Check ingress controller logs: `kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx`

**Rate limiting too aggressive:**
1. Adjust `limit-rps` annotation in the ingress resource
2. Increase `limit-burst-multiplier` for burst allowance
3. Consider per-service rate limits using separate ingress resources

### Manifest Locations

```
infrastructure/kubernetes/
├── ingress-nginx/
│   ├── values.yaml              # Helm values for NGINX Ingress Controller
│   └── custom-error-pages.yaml  # Branded 502/503/504 error pages
├── cert-manager/
│   ├── values.yaml              # Helm values for cert-manager
│   └── cluster-issuer.yaml      # Let's Encrypt ClusterIssuers (staging + prod)
├── staging/
│   └── ingress.yaml             # Staging ingress (staging.qualisys.dev)
└── production/
    └── ingress.yaml             # Production ingress (app.qualisys.io, api.qualisys.io)

infrastructure/terraform/
├── aws/dns/                     # Route 53 DNS zones and records
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
└── azure/modules/dns/           # Azure DNS zones and records
    ├── main.tf
    ├── variables.tf
    └── outputs.tf
```

## Test Database

### Overview

QUALISYS uses a dedicated test database (`qualisys_test`) with tenant isolation via Row-Level Security (RLS). The test database is separate from development and production databases to prevent data conflicts.

### Architecture

```
qualisys_test/
├── public/               # Shared schema (system tables, migrations)
├── tenant_test_1/        # Test tenant 1 (RLS-isolated)
├── tenant_test_2/        # Test tenant 2 (RLS-isolated)
└── tenant_test_3/        # Test tenant 3 (RLS-isolated)
```

### Test Tenant IDs

| Schema | Tenant UUID |
|--------|-------------|
| `tenant_test_1` | `11111111-1111-1111-1111-111111111111` |
| `tenant_test_2` | `22222222-2222-2222-2222-222222222222` |
| `tenant_test_3` | `33333333-3333-3333-3333-333333333333` |

### Local Setup

1. Start the test database container:

```bash
# Using Docker
docker run -d --name qualisys-postgres-test \
  -e POSTGRES_DB=qualisys_test \
  -e POSTGRES_USER=test_user \
  -e POSTGRES_PASSWORD=test_password \
  -p 5433:5432 \
  postgres:15-alpine

# Using Podman (10Pearls workstations)
podman run -d --name qualisys-postgres-test \
  -e POSTGRES_DB=qualisys_test \
  -e POSTGRES_USER=test_user \
  -e POSTGRES_PASSWORD=test_password \
  -p 5433:5432 \
  postgres:15-alpine
```

2. Initialize tenant schemas and RLS policies:

```bash
PGPASSWORD=test_password psql \
  -h localhost -p 5433 -U test_user -d qualisys_test \
  -f infrastructure/scripts/init-test-db.sql
```

3. Copy the environment template:

```bash
cp .env.test.example .env.test
# Edit .env.test if needed (defaults work for local Docker/Podman)
```

4. Run database migrations:

```bash
npm run db:migrate:test
```

### Test Database Commands

```bash
# Reset test database (truncate all tables, preserve schemas)
npm run db:reset:test

# Run RLS isolation verification
npm run db:isolation:test

# Run integration tests
npm run test:integration
```

### Database Reset

The reset script (`scripts/db-reset.ts`) truncates all tables in test tenant schemas while preserving:
- Schema structure (tables, columns, constraints)
- RLS policies
- Indexes

**Safety check**: The script refuses to run against production databases (connection strings containing `qualisys_master` or `production`).

**Performance target**: Reset completes in <30 seconds.

### RLS Isolation Verification

The isolation test script (`infrastructure/scripts/isolation-test.sql`) verifies:

1. `test_user` has NO SUPERUSER, NO BYPASSRLS
2. RLS is enabled on tenant tables
3. RLS policies exist
4. Tenant 1 data is invisible to Tenant 2
5. Tenant 2 data is invisible to Tenant 1
6. Tenant 3 isolation is verified

Run manually:

```bash
PGPASSWORD=test_password psql \
  -h localhost -p 5433 -U test_user -d qualisys_test \
  -f infrastructure/scripts/isolation-test.sql
```

### CI/CD Integration

In GitHub Actions, the test database is provisioned automatically:

1. PostgreSQL 15 service container starts with `qualisys_test` database
2. `init-test-db.sql` creates tenant schemas and RLS policies
3. Migrations run against the test database
4. Integration tests execute with `TEST_DATABASE_URL` set

### Writing Integration Tests with Tenant Isolation

When writing tests that involve tenant data, set the tenant context:

```typescript
// In your test setup
beforeEach(async () => {
  await client.query(`SET app.current_tenant = '${TEST_TENANT_1_ID}'`);
});

afterEach(async () => {
  await client.query(`RESET app.current_tenant`);
});
```

### Test Database Troubleshooting

**Cannot connect to test database:**
1. Verify container is running: `docker ps` or `podman ps`
2. Check port mapping: test database uses port 5433 (not 5432)
3. Verify credentials: `test_user` / `test_password`

**RLS blocking test queries:**
1. Ensure `app.current_tenant` is set before querying tenant tables
2. Use the correct tenant UUID for the schema you're querying
3. Verify RLS policies exist: `SELECT * FROM pg_policies WHERE schemaname = 'tenant_test_1'`

**Reset script failing:**
1. Check `TEST_DATABASE_URL` environment variable is set
2. Verify the connection string points to `qualisys_test` (not `qualisys_master`)
3. Check database container is healthy: `pg_isready -h localhost -p 5433 -U test_user`

## Test Data Factories

### Quick Start

```bash
# Seed the test database with baseline data
npm run db:seed:test

# Fresh database: reset + migrate + seed
npm run db:fresh
```

### Available Factories

| Factory | Description | Example |
|---------|-------------|---------|
| `UserFactory` | Users with roles | `UserFactory.create({ role: 'admin' })` |
| `OrganizationFactory` | Orgs with tenant schemas | `OrganizationFactory.create({ plan: 'pro' })` |
| `ProjectFactory` | Projects with config | `ProjectFactory.create({ organizationId })` |
| `TeamFactory` | Teams with members | `TeamFactory.create({ memberIds })` |
| `TestCaseFactory` | Test cases with steps | `TestCaseFactory.create({ stepsCount: 5 })` |
| `TestSuiteFactory` | Test suites grouping cases | `TestSuiteFactory.create({ testCaseIds })` |
| `TestExecutionFactory` | Execution records | `TestExecutionFactory.create({ status: 'passed' })` |
| `TestEvidenceFactory` | Screenshots, videos, logs | `TestEvidenceFactory.create({ type: 'screenshot' })` |
| `DefectFactory` | Bug reports | `DefectFactory.create({ severity: 'critical' })` |

### Factory Usage in Tests

```typescript
import { UserFactory, createTenantGraph } from '../factories';

// Create a single entity
const user = UserFactory.create({ role: 'admin' });

// Create multiple entities
const users = UserFactory.createMany(5, { organizationId: org.id });

// Create a full tenant graph (org + users + projects + team)
const graph = createTenantGraph({
  tenantId: '11111111-1111-1111-1111-111111111111',
  userCount: 3,
  projectCount: 2,
});
// graph.organization, graph.users, graph.projects, graph.teams
```

### Seed Data Structure

After running `npm run db:seed:test`:

| Tenant | Schema | Users | Projects | Test Cases | Executions |
|--------|--------|-------|----------|------------|------------|
| Acme Corp | `tenant_test_1` | 4 (1 admin) | 3 | 15 | 15 |
| Globex Inc | `tenant_test_2` | 3 (1 admin) | 1 | 5 | 5 |
| Initech LLC | `tenant_test_3` | 3 (1 admin) | 1 | 5 | 5 |
| **Total** | | **10** | **5** | **25** | **25** |

### Idempotent Seeding

The seed script uses `ON CONFLICT DO UPDATE` for all inserts:
- Running `npm run db:seed:test` multiple times is safe
- Existing records are updated, not duplicated
- Faker is seeded with a fixed value (`42`) for deterministic data

### Factory Directory Structure

```
factories/
├── index.ts                 # Public API exports
├── UserFactory.ts           # User entity factory (AC2)
├── OrganizationFactory.ts   # Organization entity factory (AC3)
├── ProjectFactory.ts        # Project entity factory (AC4)
├── TeamFactory.ts           # Team entity factory
├── TestCaseFactory.ts       # Test case with steps (AC5)
├── TestSuiteFactory.ts      # Test suite factory
├── TestExecutionFactory.ts  # Execution records (AC6)
├── TestEvidenceFactory.ts   # Screenshots, videos, logs
├── DefectFactory.ts         # Bug report factory
└── helpers.ts               # createTenantGraph, createProjectGraph (AC8)
types/
└── entities.ts              # TypeScript entity type definitions
scripts/
└── seed.ts                  # Idempotent seed script (AC7, AC9)
```

## Multi-Tenant Test Isolation

### Overview

All integration and E2E tests run inside isolated tenant schemas. Each test (or test suite) gets a unique schema with full RLS policies, ensuring zero data leakage between tests — even under parallel execution.

### Tenant Isolation Utilities

| Function | Description |
|----------|-------------|
| `createTestTenant(pool, tenantId?)` | Creates a schema with users, projects, test_cases, test_executions tables + RLS policies |
| `cleanupTestTenant(pool, tenantId)` | Drops the schema with CASCADE and verifies removal |
| `setTenantContext(client, tenantId)` | Sets `app.current_tenant` via `SET LOCAL` (transaction-scoped) |
| `clearTenantContext(client)` | Resets the tenant context |
| `requireTenantContext(client)` | Throws if no tenant context is set |
| `seedTestTenant(client, schema, tenantId)` | Inserts minimal seed data (1 user, 1 project) |

### Using in Jest Tests

**Option A: describe-level fixture (recommended)**

```typescript
import { useTenantIsolation } from '../src/test-utils';

describe('MyService', () => {
  const ctx = useTenantIsolation();

  test('creates a record', async () => {
    const { client, schemaName, tenantId } = ctx.current();
    await client.query(`INSERT INTO ${schemaName}.users ...`);
  });
});
```

**Option B: per-test decorator**

```typescript
import { withTenantIsolation } from '../src/test-utils';

test('isolated test', withTenantIsolation(async ({ client, schemaName }) => {
  const res = await client.query(`SELECT * FROM ${schemaName}.users`);
  expect(res.rows).toHaveLength(0);
}));
```

### Using in Pytest

```python
# The test_tenant and tenant_connection fixtures are in tests/conftest.py

def test_something(test_tenant, tenant_connection):
    # test_tenant = {"tenant_id": "...", "schema_name": "..."}
    # tenant_connection = asyncpg connection with app.current_tenant set
    pass
```

### Parallel Test Safety

Each test worker gets a UUID-based tenant ID (`test_<uuid>`), so parallel Jest workers or pytest-xdist workers never share schemas. The `tenant-isolation` Jest project in `jest.config.js` runs integration tests from `tests/integration/`.

### Directory Structure

```
src/test-utils/
├── tenant-isolation.ts   # Core provisioning, cleanup, context utilities
├── tenant-fixtures.ts    # Jest hooks (useTenantIsolation, withTenantIsolation)
└── index.ts              # Public exports
tests/
├── integration/
│   └── tenant-isolation.test.ts  # RLS isolation verification tests
└── conftest.py           # Pytest fixtures for Python tests
```

## Monitoring & Metrics

### Application Metrics

QUALISYS uses Prometheus for metrics collection. The `api/src/metrics/prometheus.ts` module provides Express middleware that automatically instruments all HTTP requests.

```typescript
import { metricsMiddleware, metricsHandler } from './metrics/prometheus';

// Add to Express app (before route handlers)
app.use(metricsMiddleware);
app.get('/metrics', metricsHandler);
```

### Metrics Exposed

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `http_requests_total` | Counter | method, route, status | Request count |
| `http_request_duration_seconds` | Histogram | method, route, status | Latency (p50, p95, p99) |
| `http_requests_in_flight` | Gauge | — | Active requests |
| Default Node.js metrics | Various | — | Heap, GC, event loop |

### Grafana Dashboards

Access Grafana at `https://grafana.qualisys.io`. Three custom dashboards are available:

- **Cluster Overview** — Node CPU/memory/disk, pod counts, restarts, resource utilization
- **Application Performance** — Request rate, error rate, latency percentiles (RED metrics)
- **Database & Cache** — PostgreSQL connections, TPS, cache hit rate; Redis memory, ops/s

### Alert Rules

Alert rules fire to Slack (`#alerts` and `#alerts-critical`):

| Alert | Threshold | Channel |
|-------|-----------|---------|
| Pod crash loop | >3 restarts in 5min | #alerts-critical |
| High CPU/memory | >80% for 5min | #alerts |
| DB connection pool | >90% max connections | #alerts-critical |
| API latency (p95) | >500ms for 5min | #alerts |

### Monitoring Files

```
infrastructure/kubernetes/monitoring/
├── namespace.yaml                    # monitoring namespace
├── kube-prometheus-stack-values.yaml  # Helm values
├── servicemonitors.yaml              # Application scraping
├── postgres-exporter.yaml            # PostgreSQL exporter
├── redis-exporter.yaml               # Redis exporter
├── alert-rules.yaml                  # PrometheusRule CRD
└── grafana-dashboards/
    ├── cluster-overview-dashboard.yaml
    ├── application-dashboard.yaml
    └── database-dashboard.yaml
api/src/metrics/
└── prometheus.ts                     # Express metrics middleware
```

## Logging

### Structured Logger

QUALISYS uses Pino for structured JSON logging. All logs include `timestamp`, `level`, `message`, `trace_id`, and `tenant_id` fields for cross-service correlation and tenant-scoped debugging.

```typescript
import { loggingMiddleware } from './logger';

// Add to Express app (before route handlers)
app.use(loggingMiddleware);
```

The middleware automatically:
- Extracts `trace_id` from `X-Request-ID` header (or generates a UUID)
- Extracts `tenant_id` from `X-Tenant-ID` header
- Logs every HTTP request/response with method, path, status, and duration
- Attaches a per-request `Logger` instance to `req.log`

### Using the Logger in Handlers

```typescript
// Per-request logger (has trace_id + tenant_id set)
app.get('/api/test-cases', (req, res) => {
  (req as any).log.info('Fetching test cases', { count: 42 });
});

// Standalone logger (for startup, background jobs)
import { logger } from './logger';
logger.info('Server started', { port: 3000 });
```

### PII Redaction

Fluent Bit applies PII redaction before logs reach the central system:
- **Emails**: `john@example.com` → `j***@***.com`
- **Names**: `John Smith` → `John S***`

### Log Search

- **AWS**: CloudWatch Logs Insights at `console.aws.amazon.com/cloudwatch`
- **Azure**: Log Analytics at `portal.azure.com` → Log Analytics workspaces

### Logging Files

```
infrastructure/kubernetes/logging/
├── fluent-bit-configmap.yaml   # Fluent Bit config, parsers, PII Lua script
└── fluent-bit-daemonset.yaml   # DaemonSet + ServiceAccount + RBAC
infrastructure/terraform/aws/logging/
├── main.tf                     # CloudWatch log groups, KMS, IRSA
├── alerts.tf                   # Metric filters, alarms, SNS
├── variables.tf
└── outputs.tf
infrastructure/terraform/azure/modules/logging/
├── main.tf                     # Log Analytics, alert rules, Workload Identity
├── variables.tf
└── outputs.tf
api/src/logger/
└── index.ts                    # Pino structured logger + Express middleware
```

## CI/CD Test Pipeline

### Pipeline Overview

The PR Checks workflow (`.github/workflows/pr-checks.yml`) runs on every pull request to `main`. Tests execute in parallel after lint/format/type gates pass.

### Job Structure

```
lint + format-check + type-check (parallel gates)
         │
         ├── unit-tests (Node 18 + 20 matrix)
         ├── integration-tests (PostgreSQL + Redis)
         └── e2e-tests (Playwright chromium-critical)
                    │
              test-summary (PR comment)
```

### Node.js Matrix

Unit tests run against Node.js **18** and **20** with `fail-fast: false` — both versions complete even if one fails. Coverage and Codecov upload run on Node 20 only.

### Flaky Test Handling

| Framework | Retry Count | Configuration |
|-----------|-------------|---------------|
| Jest (unit + integration) | 3 retries | `retryTimes: 3` in `jest.config.js` (CI only) |
| Playwright (E2E) | 2 retries | `retries: 2` in `playwright.config.ts` (CI only) |

**Investigating flaky tests:**
1. Check the workflow run for retry annotations in test logs
2. Download test artifacts from the Actions tab (retained 30 days)
3. Look for timing-dependent assertions or external service calls
4. Add `@flaky` tag to known flaky tests for tracking
5. File a bug if a test fails intermittently more than 3 times per week

### Test Artifacts

All test artifacts are retained for **30 days**:
- `unit-test-results-node-{18,20}` — JUnit XML + coverage reports
- `integration-test-results` — JUnit XML
- `playwright-report` — HTML report + screenshots/videos

### Coverage Threshold

The 80% line coverage threshold is enforced in `jest.config.js`:
- Build fails if coverage drops below threshold
- Coverage is uploaded to [Codecov](https://codecov.io) on every PR
- Coverage diff is shown in the PR test summary comment

### Timeouts

| Job | Timeout |
|-----|---------|
| Unit Tests | 15 minutes |
| Integration Tests | 15 minutes |
| E2E Tests | 10 minutes (5 min test step) |

## Test Reporting Dashboard

### Allure Reports

Test results are published to the [Allure Dashboard](https://reports.qualisys.io) after every PR check run. The dashboard provides:

- **Trend Charts**: Pass/fail trends and execution time over the last 30 days
- **Flaky Test Detection**: Tests with intermittent failures are flagged automatically
- **Suite Filtering**: Filter results by unit, integration, or E2E test suites
- **Build Summary**: Latest build status with pass rate at a glance

### Local Allure Reports

```bash
# Generate a local Allure report (requires allure-commandline)
npm run allure:generate
npm run allure:open
```

### Coverage Trends

Coverage is tracked via [Codecov](https://codecov.io). Configuration is in `codecov.yml`:
- Project target: 80% with 2% threshold
- Patch target: 80%
- PR comments show coverage diff with file-level details

## Third-Party Secrets

### Accessing Secrets in Code

Secrets are synced from cloud secret stores to K8s Secrets via ExternalSecrets Operator. Reference in deployment manifests:

```yaml
env:
  - name: OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: openai-api-key
        key: api-key
```

### Adding a New Secret

1. Add Terraform resource in `infrastructure/terraform/aws/secrets/main.tf` (and Azure module)
2. Add ExternalSecret in `infrastructure/kubernetes/secrets/external-secrets.yaml`
3. Update IAM policy in `infrastructure/terraform/aws/secrets/iam.tf`
4. Update `docs/secrets/README.md` with provisioning steps and rotation schedule
5. **Never** commit real secret values — use `REPLACE_WITH_*` placeholders

### Rotation

See `docs/secrets/README.md` for the full rotation schedule and procedures. LLM keys rotate quarterly; all others yearly.

## Local Development Environment

### Prerequisites

- **Podman Desktop 1.x+** or Podman CLI 4.x+ (Docker Desktop is NOT approved per 10Pearls policy)
- **podman-compose** (`pip install podman-compose` or bundled with Podman Desktop)

### Quick Start

```bash
cp .env.example .env
podman-compose up -d
podman-compose exec api npx ts-node scripts/dev-seed.ts
```

- **Web**: http://localhost:3000
- **API**: http://localhost:3001
- **MailCatcher**: http://localhost:1080
- **Test credentials**: `admin@tenant-dev-1.test` / `password123`

### Hot Reload

- **API**: `ts-node-dev --respawn --poll` watches `api/src/` — saves trigger restart
- **Web**: Next.js Fast Refresh watches `web/src/` — changes appear instantly

### Common Commands

```bash
podman-compose logs -f api         # Follow API logs
podman-compose down -v             # Reset everything (removes DB data)
podman-compose up -d --build       # Rebuild after Containerfile changes
podman-compose exec postgres psql -U qualisys -d qualisys_master  # DB shell
```

### Files

| File | Purpose |
|------|---------|
| `compose.yml` | All local services |
| `.env.example` | Environment template |
| `api/Containerfile.dev` | API dev container |
| `web/Containerfile.dev` | Web dev container |
| `scripts/init-local-db.sql` | DB schema init |
| `scripts/dev-seed.ts` | Dev seed data |
| `docs/local-development.md` | Full guide + troubleshooting |

## Code Style

### TypeScript / JavaScript
- ESLint with project config.
- Prettier for formatting.
- Strict TypeScript (`noEmit` type checking).

### Python
- Ruff for linting.
- Black for formatting.
- mypy for type checking.

## Getting Help

- Check [docs/index.md](./docs/index.md) for project documentation.
- Review the relevant [tech spec](./docs/tech-specs/) for your epic.
- Ask in the project Slack channel.
