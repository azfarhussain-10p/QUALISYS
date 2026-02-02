# Story 0.17: Test Reporting Dashboard

Status: ready-for-dev

## Story

As a **QA Lead**,
I want **a test reporting dashboard**,
so that **I can track test trends, flakiness, and coverage over time**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | Test reporting tool configured (Allure Server) | Allure Server accessible at reports.qualisys.io |
| AC2 | Dashboard shows test pass/fail trends (last 30 days) | Trend chart displays daily pass/fail counts |
| AC3 | Dashboard shows test execution time trends | Execution time chart shows duration per run |
| AC4 | Dashboard identifies flaky tests (tests that fail intermittently) | Flaky test list with failure frequency displayed |
| AC5 | Dashboard shows code coverage trends (line, branch, function) | Coverage chart shows metrics over time |
| AC6 | Dashboard accessible to team at https://reports.qualisys.io | Team members can access dashboard with authentication |
| AC7 | Test results automatically published from CI/CD pipeline | Workflow uploads results to Allure Server |
| AC8 | Historical test data retained for 90 days | Data older than 90 days automatically purged |
| AC9 | Dashboard supports filtering by test suite (unit, integration, E2E) | Filter dropdown allows suite selection |
| AC10 | Dashboard shows latest build status and quick summary | Landing page shows current health at a glance |

## Tasks / Subtasks

- [ ] **Task 1: Allure Server Deployment** (AC: 1, 6)
  - [ ] 1.1 Create Kubernetes deployment for Allure Server
  - [ ] 1.2 Configure persistent volume for test results storage
  - [ ] 1.3 Create Allure Server service and ingress
  - [ ] 1.4 Configure SSL certificate via cert-manager
  - [ ] 1.5 Set up basic authentication or OAuth integration
  - [ ] 1.6 Document deployment configuration

- [ ] **Task 2: CI/CD Integration** (AC: 7)
  - [ ] 2.1 Add Allure reporter to Jest configuration
  - [ ] 2.2 Add Allure reporter to Playwright configuration
  - [ ] 2.3 Create workflow step to generate Allure report
  - [ ] 2.4 Create workflow step to upload results to Allure Server
  - [ ] 2.5 Configure project/suite identification in reports
  - [ ] 2.6 Test end-to-end report publishing

- [ ] **Task 3: Test Trend Dashboards** (AC: 2, 3, 10)
  - [ ] 3.1 Configure pass/fail trend visualization
  - [ ] 3.2 Configure execution time trend visualization
  - [ ] 3.3 Set up build history view (last 30 days)
  - [ ] 3.4 Create landing page with quick summary
  - [ ] 3.5 Configure trend aggregation intervals

- [ ] **Task 4: Flaky Test Detection** (AC: 4)
  - [ ] 4.1 Configure Allure retry tracking
  - [ ] 4.2 Set up flaky test identification rules
  - [ ] 4.3 Create flaky test report view
  - [ ] 4.4 Configure flaky test notifications
  - [ ] 4.5 Document flaky test investigation workflow

- [ ] **Task 5: Coverage Integration** (AC: 5)
  - [ ] 5.1 Configure coverage report upload to Allure
  - [ ] 5.2 Integrate Codecov for coverage trends
  - [ ] 5.3 Add coverage badge generation
  - [ ] 5.4 Configure coverage diff in PR comments
  - [ ] 5.5 Set up coverage trend visualization

- [ ] **Task 6: Data Retention and Filtering** (AC: 8, 9)
  - [ ] 6.1 Configure 90-day retention policy
  - [ ] 6.2 Set up automated cleanup job
  - [ ] 6.3 Configure suite filtering (unit, integration, E2E)
  - [ ] 6.4 Add date range filtering
  - [ ] 6.5 Test retention policy execution

## Dev Notes

### Architecture Alignment

This story implements test reporting infrastructure per the architecture document:

- **Visibility**: Dashboard provides QA Lead with test health overview
- **Trend Analysis**: Historical data enables pattern identification
- **Flaky Detection**: Identifies unreliable tests for remediation
- **Coverage Tracking**: Monitors code coverage trends over time

### Technical Constraints

- **Tool Choice**: Allure Server (open-source, self-hosted)
- **Data Retention**: 90 days for historical test data
- **Access**: Team-wide access at https://reports.qualisys.io
- **Integration**: Must work with Jest and Playwright reporters
- **Storage**: Persistent volume for test result artifacts

### Allure Server Kubernetes Deployment

```yaml
# allure-server-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: allure-server
  namespace: test-infrastructure
spec:
  replicas: 1
  selector:
    matchLabels:
      app: allure-server
  template:
    metadata:
      labels:
        app: allure-server
    spec:
      containers:
        - name: allure-server
          image: frankescobar/allure-docker-service:2.21.0
          ports:
            - containerPort: 5050
          env:
            - name: CHECK_RESULTS_EVERY_SECONDS
              value: "30"
            - name: KEEP_HISTORY
              value: "25"
            - name: KEEP_HISTORY_LATEST
              value: "10"
          volumeMounts:
            - name: allure-results
              mountPath: /app/allure-results
            - name: allure-reports
              mountPath: /app/default-reports
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /allure-docker-service/version
              port: 5050
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /allure-docker-service/version
              port: 5050
            initialDelaySeconds: 10
            periodSeconds: 5
      volumes:
        - name: allure-results
          persistentVolumeClaim:
            claimName: allure-results-pvc
        - name: allure-reports
          persistentVolumeClaim:
            claimName: allure-reports-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: allure-server
  namespace: test-infrastructure
spec:
  selector:
    app: allure-server
  ports:
    - port: 5050
      targetPort: 5050
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: allure-server-ingress
  namespace: test-infrastructure
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/auth-type: basic
    nginx.ingress.kubernetes.io/auth-secret: allure-basic-auth
    nginx.ingress.kubernetes.io/auth-realm: "Allure Reports - Authentication Required"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - reports.qualisys.io
      secretName: allure-tls
  rules:
    - host: reports.qualisys.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: allure-server
                port:
                  number: 5050
```

### Persistent Volume Configuration

```yaml
# allure-pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: allure-results-pvc
  namespace: test-infrastructure
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: gp3
  resources:
    requests:
      storage: 20Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: allure-reports-pvc
  namespace: test-infrastructure
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: gp3
  resources:
    requests:
      storage: 50Gi
```

### Jest Allure Configuration

```javascript
// jest.config.js (additions)
module.exports = {
  // ... existing config
  reporters: [
    'default',
    ['jest-junit', { outputDirectory: './test-results' }],
    ['jest-allure', {
      outputDir: 'allure-results',
      disableWebdriverStepsReporting: true,
      disableWebdriverScreenshotsReporting: false,
    }],
  ],
  setupFilesAfterEnv: ['jest-allure/dist/setup'],
};
```

### Playwright Allure Configuration

```typescript
// playwright.config.ts (additions)
import { defineConfig } from '@playwright/test';

export default defineConfig({
  // ... existing config
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['junit', { outputFile: 'test-results/e2e/junit.xml' }],
    ['allure-playwright', {
      outputFolder: 'allure-results',
      suiteTitle: 'E2E Tests',
    }],
  ],
});
```

### CI/CD Workflow Addition

```yaml
# Addition to .github/workflows/pr-checks.yml
  publish-allure-report:
    needs: [unit-tests, integration-tests, e2e-tests]
    if: always()
    runs-on: ubuntu-latest
    steps:
      - name: Download all test results
        uses: actions/download-artifact@v4
        with:
          path: allure-results

      - name: Merge Allure results
        run: |
          mkdir -p merged-allure-results
          find allure-results -name "*.json" -exec cp {} merged-allure-results/ \;
          find allure-results -name "*.txt" -exec cp {} merged-allure-results/ \;
          find allure-results -name "*.png" -exec cp {} merged-allure-results/ \;

      - name: Upload to Allure Server
        run: |
          curl -X POST \
            -H "Content-Type: multipart/form-data" \
            -F "results=@merged-allure-results" \
            "https://reports.qualisys.io/allure-docker-service/send-results?project_id=qualisys"

      - name: Generate Allure Report
        run: |
          curl -X GET \
            "https://reports.qualisys.io/allure-docker-service/generate-report?project_id=qualisys"

      - name: Post Report Link to PR
        uses: actions/github-script@v7
        if: github.event_name == 'pull_request'
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## Allure Test Report\n\n[View Full Report](https://reports.qualisys.io/allure-docker-service/projects/qualisys/reports/latest)`
            });
```

### Codecov Integration

```yaml
# codecov.yml
coverage:
  precision: 2
  round: down
  range: "70...100"
  status:
    project:
      default:
        target: 80%
        threshold: 2%
    patch:
      default:
        target: 80%

comment:
  layout: "reach,diff,flags,files"
  behavior: default
  require_changes: true

flags:
  unit:
    paths:
      - src/
    carryforward: true
  integration:
    paths:
      - src/
    carryforward: true
```

### Data Retention CronJob

```yaml
# allure-cleanup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: allure-cleanup
  namespace: test-infrastructure
spec:
  schedule: "0 2 * * *"  # Run daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: cleanup
              image: alpine:3.18
              command:
                - /bin/sh
                - -c
                - |
                  # Delete reports older than 90 days
                  find /app/allure-results -type f -mtime +90 -delete
                  find /app/default-reports -type d -mtime +90 -exec rm -rf {} +
              volumeMounts:
                - name: allure-results
                  mountPath: /app/allure-results
                - name: allure-reports
                  mountPath: /app/default-reports
          restartPolicy: OnFailure
          volumes:
            - name: allure-results
              persistentVolumeClaim:
                claimName: allure-results-pvc
            - name: allure-reports
              persistentVolumeClaim:
                claimName: allure-reports-pvc
```

### Package.json Dependencies

```json
{
  "devDependencies": {
    "jest-allure": "^0.1.3",
    "allure-playwright": "^2.9.0",
    "allure-commandline": "^2.24.0"
  },
  "scripts": {
    "allure:generate": "allure generate allure-results --clean -o allure-report",
    "allure:open": "allure open allure-report",
    "allure:serve": "allure serve allure-results"
  }
}
```

### Project Structure Notes

```
/
├── .github/
│   └── workflows/
│       └── pr-checks.yml         # Updated with Allure upload
├── k8s/
│   └── test-infrastructure/
│       ├── allure-deployment.yaml
│       ├── allure-pvc.yaml
│       ├── allure-ingress.yaml
│       └── allure-cleanup-cronjob.yaml
├── jest.config.js                # Updated with Allure reporter
├── playwright.config.ts          # Updated with Allure reporter
├── codecov.yml                   # Codecov configuration
├── allure-results/               # Local Allure results (gitignored)
└── allure-report/                # Local Allure report (gitignored)
```

### Dependencies

- **Story 0.16** (CI/CD Test Pipeline) - REQUIRED: Test results generation
- **Story 0.13** (Load Balancer/Ingress) - REQUIRED: Ingress configuration
- Outputs used by subsequent stories:
  - Epic 1-5: Test visibility for all feature development
  - QA Lead dashboard for test health monitoring

### Security Considerations

1. **Threat: Unauthorized access** → Basic auth or OAuth required
2. **Threat: Data exposure** → TLS encryption for all traffic
3. **Threat: Storage exhaustion** → 90-day retention policy with automated cleanup
4. **Threat: Injection via test names** → Allure sanitizes test metadata

### Dashboard Views

| View | Description | Data Source |
|------|-------------|-------------|
| **Overview** | Latest build status, pass rate, coverage | Allure aggregation |
| **Trends** | 30-day pass/fail and execution time | Allure history |
| **Flaky Tests** | Tests with intermittent failures | Allure retry analysis |
| **Coverage** | Line, branch, function coverage over time | Codecov API |
| **Suites** | Filter by unit/integration/E2E | Allure project filtering |

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#Test-Infrastructure]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.17]
- [Source: docs/architecture/architecture.md#Testing-Strategy]
- [Allure Server Documentation](https://github.com/fescobar/allure-docker-service)

## Dev Agent Record

### Context Reference

- [docs/stories/0-17-test-reporting-dashboard.context.xml](./0-17-test-reporting-dashboard.context.xml)

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
| 2026-01-24 | SM Agent (Bob) | Context XML generated, status: drafted → ready-for-dev |
