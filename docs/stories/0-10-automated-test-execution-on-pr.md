# Story 0.10: Automated Test Execution on PR

Status: ready-for-dev

## Story

As a **Developer**,
I want **tests to run automatically on every PR with coverage reporting**,
so that **we catch bugs before merging to main and maintain code quality standards**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | PR checks workflow runs all test suites: unit, integration, E2E subset | GitHub Actions logs show all test jobs executed |
| AC2 | Test results posted as PR comment with pass/fail status | PR comment shows test summary table |
| AC3 | Coverage report shows line coverage percentage (target: 80%) | Coverage badge/report shows percentage |
| AC4 | PR cannot merge if tests fail (branch protection rule) | Merge button disabled when tests fail |
| AC5 | Test execution time <10 minutes total (parallelized) | GitHub Actions summary shows <10 min |
| AC6 | Failed tests show clear error messages and stack traces | PR comment includes failure details |
| AC7 | Flaky test detection: retry failed tests 3x before marking failed | Workflow includes retry logic |
| AC8 | Coverage report uploaded to Codecov or similar service | Codecov dashboard shows project coverage |
| AC9 | Test matrix includes multiple Node.js/Python versions | Workflow uses matrix strategy |
| AC10 | Integration tests use test database from Story 0.14 | Tests connect to dedicated test DB |

## Tasks / Subtasks

- [ ] **Task 1: Test Framework Configuration** (AC: 1, 5)
  - [ ] 1.1 Configure Jest/Vitest for unit tests with coverage
  - [ ] 1.2 Configure integration test framework (Supertest/pytest)
  - [ ] 1.3 Configure Playwright for E2E tests (critical paths subset)
  - [ ] 1.4 Set up test scripts in package.json/pyproject.toml
  - [ ] 1.5 Configure parallel test execution (Jest --maxWorkers, pytest-xdist)

- [ ] **Task 2: Unit Test Job** (AC: 1, 3, 5, 9)
  - [ ] 2.1 Add unit-tests job to pr-checks.yml
  - [ ] 2.2 Configure test matrix for Node.js 18, 20
  - [ ] 2.3 Run tests with coverage collection
  - [ ] 2.4 Generate coverage report (lcov, cobertura)
  - [ ] 2.5 Upload coverage artifacts

- [ ] **Task 3: Integration Test Job** (AC: 1, 5, 10)
  - [ ] 3.1 Add integration-tests job to pr-checks.yml
  - [ ] 3.2 Configure test database service container (PostgreSQL)
  - [ ] 3.3 Run database migrations before tests
  - [ ] 3.4 Execute API integration tests
  - [ ] 3.5 Clean up test data after completion

- [ ] **Task 4: E2E Test Job** (AC: 1, 5)
  - [ ] 4.1 Add e2e-tests job to pr-checks.yml
  - [ ] 4.2 Configure Playwright with headless browsers
  - [ ] 4.3 Run critical path E2E tests only (login, core flows)
  - [ ] 4.4 Upload test artifacts (screenshots, videos on failure)
  - [ ] 4.5 Configure timeout for E2E tests (5 min max)

- [ ] **Task 5: PR Comment and Reporting** (AC: 2, 6, 8)
  - [ ] 5.1 Configure test reporter action (dorny/test-reporter)
  - [ ] 5.2 Post test summary as PR comment
  - [ ] 5.3 Include failed test details with stack traces
  - [ ] 5.4 Configure Codecov integration for coverage tracking
  - [ ] 5.5 Add coverage badge to README

- [ ] **Task 6: Flaky Test Handling** (AC: 7)
  - [ ] 6.1 Configure Jest retry logic (jest.retryTimes)
  - [ ] 6.2 Configure Playwright retry (retries: 2 in config)
  - [ ] 6.3 Add retry wrapper for integration tests
  - [ ] 6.4 Log flaky test occurrences for tracking
  - [ ] 6.5 Document flaky test investigation process

- [ ] **Task 7: Branch Protection & Validation** (AC: 4, All)
  - [ ] 7.1 Configure branch protection rule for main branch
  - [ ] 7.2 Require status checks: unit-tests, integration-tests, e2e-tests
  - [ ] 7.3 Require up-to-date branches before merging
  - [ ] 7.4 Test branch protection by creating failing PR
  - [ ] 7.5 Document testing workflow in CONTRIBUTING.md

## Dev Notes

### Architecture Alignment

This story implements automated testing per the architecture document:

- **Quality Gates**: Tests must pass before merge (shift-left testing)
- **Coverage Tracking**: Maintain 80% unit test coverage minimum
- **Fast Feedback**: <10 minutes total test time for quick iteration
- **Test Isolation**: Integration tests use dedicated test database

### Technical Constraints

- **Test Time**: Total execution <10 minutes (parallelize aggressively)
- **Coverage Target**: 80% line coverage for unit tests
- **E2E Scope**: Critical paths only on PR (full suite in nightly)
- **Flaky Tests**: Retry 3x before marking failed
- **Database**: Integration tests use ephemeral test database

### Test Pyramid Strategy

```
        /\
       /  \      E2E Tests (5-10 critical paths)
      /----\     - Login flow, core user journeys
     /      \    - Run subset on PR, full in nightly
    /--------\
   /          \  Integration Tests (50-100 tests)
  /  API Tests \  - Database operations
 /--------------\ - Service interactions
/                \
/==================\ Unit Tests (500+ tests)
   Business Logic    - Pure functions, utilities
   Components        - React components (Jest/Vitest)
   Validators        - Input validation logic
```

### Test Job Configuration

```yaml
# pr-checks.yml test jobs
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: [18, 20]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
      - run: npm ci
      - run: npm test -- --coverage --maxWorkers=4
      - uses: codecov/codecov-action@v3

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
      - run: npm run test:integration

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npx playwright install --with-deps chromium
      - run: npm run test:e2e:critical
      - uses: actions/upload-artifact@v3
        if: failure()
        with:
          name: playwright-report
          path: playwright-report/
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
```

### Coverage Configuration

```javascript
// jest.config.js
module.exports = {
  collectCoverage: true,
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 80,
      lines: 80,
      statements: 80
    }
  },
  coverageReporters: ['text', 'lcov', 'cobertura'],
  coveragePathIgnorePatterns: [
    '/node_modules/',
    '/__tests__/',
    '/dist/'
  ]
};
```

### Flaky Test Retry Configuration

```javascript
// jest.config.js
module.exports = {
  // Retry failed tests up to 3 times
  retryTimes: 3,

  // Only retry in CI
  retryImmediately: process.env.CI === 'true'
};

// playwright.config.ts
export default defineConfig({
  retries: process.env.CI ? 2 : 0,
  reporter: [
    ['html'],
    ['junit', { outputFile: 'results.xml' }]
  ]
});
```

### Branch Protection Rules

```
Branch: main
- Require status checks before merging: ✓
  - Required checks:
    - unit-tests (Node.js 18)
    - unit-tests (Node.js 20)
    - integration-tests
    - e2e-tests
- Require branches to be up to date: ✓
- Require conversation resolution: ✓
- Require signed commits: Optional
- Include administrators: ✓
```

### Project Structure Notes

```
/
├── api/
│   ├── src/
│   └── __tests__/
│       ├── unit/           # Unit tests
│       └── integration/    # API integration tests
├── web/
│   ├── src/
│   └── __tests__/
│       └── unit/           # Component tests
├── e2e/
│   ├── tests/
│   │   ├── critical/       # Critical path tests (run on PR)
│   │   └── full/           # Full suite (nightly)
│   └── playwright.config.ts
├── .github/
│   └── workflows/
│       └── pr-checks.yml   # Updated with test jobs
└── jest.config.js          # Test configuration
```

### Dependencies

- **Story 0.8** (GitHub Actions) - REQUIRED: pr-checks.yml workflow
- **Story 0.14** (Test Database) - REQUIRED for integration tests
- Outputs used by subsequent stories:
  - Story 0.16 (CI/CD Test Pipeline): Test configuration and patterns
  - Story 0.17 (Test Reporting Dashboard): Test result formats

### Security Considerations

1. **Test Database Isolation**: Use dedicated test database, never production
2. **Secret Handling**: Test secrets stored in GitHub Actions secrets
3. **Artifact Retention**: Test artifacts auto-deleted after 30 days
4. **Coverage Reports**: No sensitive data in coverage reports

### Performance Optimization

| Technique | Impact | Implementation |
|-----------|--------|----------------|
| Parallel execution | 3-4x faster | Jest --maxWorkers, pytest-xdist |
| Test sharding | 2x faster | Split E2E across runners |
| Service containers | No setup time | PostgreSQL as GitHub Actions service |
| Dependency caching | 30s faster | actions/cache for node_modules |
| Selective E2E | 5x faster | Critical paths only on PR |

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#CI-CD-Pipeline-Sequence]
- [Source: docs/tech-specs/tech-spec-epic-0.md#Test-Infrastructure]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.10]
- [Source: docs/architecture/architecture.md#Testing-Strategy]

## Dev Agent Record

### Context Reference

- [docs/stories/0-10-automated-test-execution-on-pr.context.xml](./0-10-automated-test-execution-on-pr.context.xml)

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
