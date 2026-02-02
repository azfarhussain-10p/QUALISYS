# Story 0.16: CI/CD Test Pipeline Integration

Status: ready-for-dev

## Story

As a **Developer**,
I want **the CI/CD pipeline to run all tests with proper reporting and parallel execution**,
so that **we have visibility into test results and fast feedback on code changes**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | GitHub Actions workflow runs tests in parallel (unit, integration, E2E) | Workflow jobs run concurrently in Actions tab |
| AC2 | Test results uploaded to GitHub Actions artifacts (JUnit XML, coverage) | Artifacts downloadable from workflow run |
| AC3 | Test summary posted as PR comment (X/Y tests passed, Z% coverage) | PR shows test summary comment |
| AC4 | Failed tests show full stack traces and error logs | PR comment includes failure details |
| AC5 | Flaky test detection enabled (retry 3x before marking failed) | Flaky tests show retry attempts in logs |
| AC6 | Test execution time tracked and optimized (target <10 min total) | Workflow summary shows total time |
| AC7 | Test matrix supports multiple Node.js versions (18, 20) | Matrix jobs visible in workflow |
| AC8 | Database migrations run before integration tests | Migration step completes in workflow |
| AC9 | Test coverage threshold enforced (80% minimum) | Build fails if coverage below threshold |
| AC10 | Test artifacts retained for 30 days | Artifact retention policy configured |

## Tasks / Subtasks

- [ ] **Task 1: Parallel Test Job Configuration** (AC: 1, 6)
  - [ ] 1.1 Create parallel jobs for unit, integration, E2E tests
  - [ ] 1.2 Configure job dependencies (integration needs DB)
  - [ ] 1.3 Optimize test splitting for parallel execution
  - [ ] 1.4 Set job timeouts to prevent hanging tests
  - [ ] 1.5 Measure and optimize for <10 min total

- [ ] **Task 2: Test Matrix Configuration** (AC: 7)
  - [ ] 2.1 Configure Node.js version matrix (18, 20)
  - [ ] 2.2 Add fail-fast: false for full matrix results
  - [ ] 2.3 Configure matrix for different test types
  - [ ] 2.4 Test matrix execution locally with act
  - [ ] 2.5 Document matrix configuration

- [ ] **Task 3: Test Artifacts and Reporting** (AC: 2, 3, 4, 10)
  - [ ] 3.1 Configure JUnit XML output for all test frameworks
  - [ ] 3.2 Upload test results as artifacts
  - [ ] 3.3 Configure dorny/test-reporter for PR comments
  - [ ] 3.4 Include stack traces in failure reports
  - [ ] 3.5 Set artifact retention to 30 days

- [ ] **Task 4: Coverage Integration** (AC: 9)
  - [ ] 4.1 Configure coverage collection in test frameworks
  - [ ] 4.2 Set 80% coverage threshold
  - [ ] 4.3 Upload coverage to Codecov
  - [ ] 4.4 Add coverage badge to README
  - [ ] 4.5 Configure coverage diff in PR comments

- [ ] **Task 5: Flaky Test Handling** (AC: 5)
  - [ ] 5.1 Configure Jest retry (retryTimes: 3)
  - [ ] 5.2 Configure Playwright retry (retries: 2)
  - [ ] 5.3 Add retry logging for flaky test tracking
  - [ ] 5.4 Create flaky test report
  - [ ] 5.5 Document flaky test investigation process

- [ ] **Task 6: Database Integration** (AC: 8)
  - [ ] 6.1 Add PostgreSQL service container to integration job
  - [ ] 6.2 Run migrations before integration tests
  - [ ] 6.3 Seed test data before tests
  - [ ] 6.4 Configure test database cleanup
  - [ ] 6.5 Document database test workflow

## Dev Notes

### Architecture Alignment

This story implements CI/CD test integration per the architecture document:

- **Fast Feedback**: Parallel execution keeps pipeline under 10 minutes
- **Quality Gates**: Coverage threshold enforces code quality standards
- **Visibility**: PR comments provide immediate test feedback
- **Reliability**: Flaky test retry reduces false failures

### Technical Constraints

- **Execution Time**: Total pipeline must complete in <10 minutes
- **Coverage Threshold**: 80% minimum for unit tests
- **Retry Limit**: 3 retries for flaky tests before failing
- **Artifact Retention**: 30 days for debugging purposes
- **Matrix**: Must test on Node.js 18 and 20

### Complete Workflow Configuration

```yaml
# .github/workflows/pr-checks.yml
name: PR Checks
on:
  pull_request:
    branches: [main, develop]

permissions:
  contents: read
  pull-requests: write
  checks: write

jobs:
  # ==========================================
  # Unit Tests (Parallel by Node version)
  # ==========================================
  unit-tests:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        node-version: [18, 20]
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js ${{ matrix.node-version }}
        uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run unit tests with coverage
        run: npm test -- --coverage --maxWorkers=4 --ci --reporters=default --reporters=jest-junit
        env:
          JEST_JUNIT_OUTPUT_DIR: ./test-results/unit
          JEST_JUNIT_OUTPUT_NAME: junit.xml

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: unit-test-results-node-${{ matrix.node-version }}
          path: test-results/unit/
          retention-days: 30

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage/lcov.info
          flags: unit-tests
          name: unit-coverage-node-${{ matrix.node-version }}

  # ==========================================
  # Integration Tests (Requires Database)
  # ==========================================
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

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run database migrations
        run: npm run db:migrate:test
        env:
          TEST_DATABASE_URL: postgresql://test_user:test_password@localhost:5432/qualisys_test

      - name: Seed test data
        run: npm run db:seed:test
        env:
          TEST_DATABASE_URL: postgresql://test_user:test_password@localhost:5432/qualisys_test

      - name: Run integration tests
        run: npm run test:integration -- --ci --reporters=default --reporters=jest-junit
        env:
          TEST_DATABASE_URL: postgresql://test_user:test_password@localhost:5432/qualisys_test
          JEST_JUNIT_OUTPUT_DIR: ./test-results/integration
          JEST_JUNIT_OUTPUT_NAME: junit.xml

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: integration-test-results
          path: test-results/integration/
          retention-days: 30

  # ==========================================
  # E2E Tests (Critical Paths Only)
  # ==========================================
  e2e-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Install Playwright browsers
        run: npx playwright install --with-deps chromium

      - name: Run E2E tests (critical paths)
        run: npm run test:e2e:critical
        env:
          CI: true

      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 30

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: e2e-test-results
          path: test-results/e2e/
          retention-days: 30

  # ==========================================
  # Test Summary Report
  # ==========================================
  test-report:
    needs: [unit-tests, integration-tests, e2e-tests]
    if: always()
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Download all test results
        uses: actions/download-artifact@v4
        with:
          path: all-test-results

      - name: Publish Test Report
        uses: dorny/test-reporter@v1
        with:
          name: Test Results
          path: 'all-test-results/**/junit.xml'
          reporter: jest-junit
          fail-on-error: true

      - name: Post PR Comment
        uses: actions/github-script@v7
        if: github.event_name == 'pull_request'
        with:
          script: |
            const fs = require('fs');

            // Read test results summary
            let summary = '## Test Results Summary\n\n';
            summary += '| Suite | Status | Details |\n';
            summary += '|-------|--------|--------|\n';

            const jobs = ['unit-tests', 'integration-tests', 'e2e-tests'];
            for (const job of jobs) {
              const status = '${{ needs[job].result }}' === 'success' ? '✅' : '❌';
              summary += `| ${job} | ${status} | See artifacts |\n`;
            }

            summary += '\n📊 [View detailed results](https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }})\n';

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: summary
            });
```

### Jest Configuration for CI

```javascript
// jest.config.js
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  collectCoverage: true,
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 80,
      lines: 80,
      statements: 80,
    },
  },
  coverageReporters: ['text', 'lcov', 'cobertura'],
  coveragePathIgnorePatterns: ['/node_modules/', '/__tests__/', '/dist/'],
  testMatch: ['**/__tests__/**/*.test.[jt]s?(x)'],
  maxWorkers: '50%',
  // Flaky test retry
  retryTimes: process.env.CI ? 3 : 0,
  // JUnit reporter for CI
  reporters: process.env.CI
    ? ['default', ['jest-junit', { outputDirectory: './test-results' }]]
    : ['default'],
};
```

### Playwright Configuration for CI

```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e/tests',
  timeout: 30000,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['junit', { outputFile: 'test-results/e2e/junit.xml' }],
  ],
  use: {
    headless: true,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
});
```

### Package.json Test Scripts

```json
{
  "scripts": {
    "test": "jest",
    "test:unit": "jest --config jest.unit.config.js",
    "test:integration": "jest --config jest.integration.config.js",
    "test:e2e": "playwright test",
    "test:e2e:critical": "playwright test --grep @critical",
    "test:coverage": "jest --coverage",
    "test:ci": "jest --ci --coverage --maxWorkers=4"
  }
}
```

### PR Comment Format

```markdown
## Test Results Summary

| Suite | Passed | Failed | Skipped | Time |
|-------|--------|--------|---------|------|
| Unit Tests | 523 | 0 | 2 | 1m 23s |
| Integration | 87 | 0 | 0 | 2m 45s |
| E2E (Critical) | 12 | 0 | 0 | 3m 12s |

**Coverage:** 84.2% (+0.3% from base)

✅ All checks passed!

📊 [View detailed results](link-to-actions-run)
```

### Project Structure Notes

```
/
├── .github/
│   └── workflows/
│       └── pr-checks.yml         # Complete test pipeline
├── jest.config.js                # Base Jest configuration
├── jest.unit.config.js           # Unit test configuration
├── jest.integration.config.js    # Integration test configuration
├── playwright.config.ts          # Playwright configuration
├── test-results/                 # JUnit XML output (gitignored)
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── coverage/                     # Coverage reports (gitignored)
└── CONTRIBUTING.md               # Updated with test pipeline docs
```

### Dependencies

- **Story 0.8** (GitHub Actions) - REQUIRED: Workflow infrastructure
- **Story 0.10** (Automated Tests on PR) - REQUIRED: Test framework setup
- **Story 0.14** (Test Database) - REQUIRED: Database for integration tests
- **Story 0.15** (Test Data Factories) - REQUIRED: Seed data for tests
- Outputs used by subsequent stories:
  - Story 0.17 (Test Reporting Dashboard): Test result data feed

### Security Considerations

1. **Threat: Secrets in logs** → Use GitHub's automatic masking
2. **Threat: Test data leakage** → Use dedicated test database
3. **Threat: Artifact exposure** → 30-day retention, then auto-delete
4. **Threat: PR from fork** → Limit permissions for fork PRs

### Performance Optimization

| Technique | Impact | Implementation |
|-----------|--------|----------------|
| Parallel jobs | 3x faster | Separate unit/integration/E2E jobs |
| Node.js cache | 30s faster | actions/setup-node with cache |
| Test splitting | 2x faster | Jest --maxWorkers, Playwright sharding |
| Selective E2E | 5x faster | Only @critical tests on PR |
| Service container | No setup time | PostgreSQL as GitHub Actions service |

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#CI-CD-Pipeline-Sequence]
- [Source: docs/tech-specs/tech-spec-epic-0.md#Test-Infrastructure]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.16]
- [Source: docs/architecture/architecture.md#Testing-Strategy]

## Dev Agent Record

### Context Reference

- [docs/stories/0-16-ci-cd-test-pipeline-integration.context.xml](./0-16-ci-cd-test-pipeline-integration.context.xml)

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
