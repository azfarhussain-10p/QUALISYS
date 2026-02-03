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
