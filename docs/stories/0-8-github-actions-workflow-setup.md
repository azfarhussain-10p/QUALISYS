# Story 0.8: GitHub Actions Workflow Setup

Status: ready-for-dev

## Story

As a **DevOps Engineer**,
I want to **configure GitHub Actions workflows for CI/CD automation**,
so that **we can automate builds, tests, and deployments on every PR and merge to main**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | PR checks workflow created: `.github/workflows/pr-checks.yml` | File exists and triggers on pull_request event |
| AC2 | Deploy staging workflow created: `.github/workflows/deploy-staging.yml` | File exists and triggers on push to main |
| AC3 | Deploy production workflow created: `.github/workflows/deploy-production.yml` | File exists with manual trigger (workflow_dispatch) |
| AC4 | PR checks workflow runs: lint, format, type-check, unit tests, integration tests | All jobs execute successfully on test PR |
| AC5 | GitHub Actions secrets configured: KUBECONFIG, AWS credentials, ECR registry | `gh secret list` shows required secrets |
| AC6 | Workflow status badges added to README | README displays CI/CD status badges |
| AC7 | Workflow permissions follow least-privilege: read-all default, write only when needed | Workflow files have explicit `permissions:` blocks |
| AC8 | Branch protection: workflow file changes require DevOps Lead approval | `.github/workflows/*.yml` changes require review |
| AC9 | GitHub Environments configured: staging, production with protection rules | `gh api repos/{owner}/{repo}/environments` shows both |
| AC10 | Reusable workflows created for common steps (build, test, deploy) | `.github/workflows/reusable-*.yml` files exist |

## Tasks / Subtasks

- [ ] **Task 1: Repository Configuration** (AC: 5, 8)
  - [ ] 1.1 Configure GitHub Actions secrets via GitHub UI or `gh secret set`
  - [ ] 1.2 Add secret: AWS_ACCESS_KEY_ID (CI/CD IAM user)
  - [ ] 1.3 Add secret: AWS_SECRET_ACCESS_KEY (CI/CD IAM user)
  - [ ] 1.4 Add secret: AWS_REGION (us-east-1)
  - [ ] 1.5 Add secret: KUBECONFIG_BASE64 (base64-encoded kubeconfig)
  - [ ] 1.6 Add secret: ECR_REGISTRY (AWS account ID.dkr.ecr.region.amazonaws.com)
  - [ ] 1.7 Configure branch protection for .github/workflows/* requiring approval

- [ ] **Task 2: GitHub Environments Setup** (AC: 9)
  - [ ] 2.1 Create GitHub Environment: staging
  - [ ] 2.2 Create GitHub Environment: production
  - [ ] 2.3 Configure production environment protection: required reviewers (DevOps Lead, Tech Lead)
  - [ ] 2.4 Configure production environment: wait timer (optional, 5 minutes)
  - [ ] 2.5 Add environment-specific secrets if needed

- [ ] **Task 3: Reusable Workflows** (AC: 10)
  - [ ] 3.1 Create `.github/workflows/reusable-build.yml` for Docker build and push
  - [ ] 3.2 Create `.github/workflows/reusable-test.yml` for running test suites
  - [ ] 3.3 Create `.github/workflows/reusable-deploy.yml` for Kubernetes deployment
  - [ ] 3.4 Document reusable workflow inputs and outputs

- [ ] **Task 4: PR Checks Workflow** (AC: 1, 4, 7)
  - [ ] 4.1 Create `.github/workflows/pr-checks.yml`
  - [ ] 4.2 Configure trigger: on pull_request to main
  - [ ] 4.3 Add job: lint (ESLint/Ruff)
  - [ ] 4.4 Add job: format-check (Prettier/Black)
  - [ ] 4.5 Add job: type-check (TypeScript/mypy)
  - [ ] 4.6 Add job: unit-tests with coverage report
  - [ ] 4.7 Add job: integration-tests (requires test database)
  - [ ] 4.8 Configure permissions: contents: read, pull-requests: write
  - [ ] 4.9 Add concurrency group to cancel outdated runs

- [ ] **Task 5: Deploy Staging Workflow** (AC: 2, 7)
  - [ ] 5.1 Create `.github/workflows/deploy-staging.yml`
  - [ ] 5.2 Configure trigger: on push to main branch
  - [ ] 5.3 Add job: build-and-push (calls reusable-build)
  - [ ] 5.4 Add job: deploy-staging (calls reusable-deploy)
  - [ ] 5.5 Configure permissions for ECR push and K8s deploy
  - [ ] 5.6 Add Slack notification on success/failure (optional)

- [ ] **Task 6: Deploy Production Workflow** (AC: 3, 7, 9)
  - [ ] 6.1 Create `.github/workflows/deploy-production.yml`
  - [ ] 6.2 Configure trigger: workflow_dispatch (manual)
  - [ ] 6.3 Add input: image_tag (required, the staging-tested image)
  - [ ] 6.4 Configure environment: production (triggers approval gate)
  - [ ] 6.5 Add job: deploy-production (calls reusable-deploy)
  - [ ] 6.6 Add job: smoke-tests (post-deployment validation)
  - [ ] 6.7 Configure permissions for K8s deploy

- [ ] **Task 7: Documentation & Validation** (AC: 6, All)
  - [ ] 7.1 Add CI/CD status badges to README.md
  - [ ] 7.2 Create test PR to validate pr-checks workflow
  - [ ] 7.3 Merge test PR to validate deploy-staging workflow
  - [ ] 7.4 Document workflow architecture in CONTRIBUTING.md
  - [ ] 7.5 Create troubleshooting guide for common CI/CD failures

## Dev Notes

### Architecture Alignment

This story implements the CI/CD foundation per the architecture document:

- **Automated Quality Gates**: PR checks prevent merging broken code
- **Continuous Deployment**: Staging auto-deploys on main branch merge
- **Controlled Production**: Manual approval gate for production deploys
- **Security**: Least-privilege permissions, protected workflow files

### Technical Constraints

- **Permissions**: All workflows must have explicit `permissions:` blocks
- **Branch Protection**: Workflow file changes require DevOps Lead approval
- **Secrets**: Never log or expose secrets in workflow output
- **Concurrency**: PR workflows cancel outdated runs to save resources
- **Reusability**: Common steps extracted to reusable workflows

### Workflow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PR Checks Workflow                        │
│  Trigger: pull_request to main                              │
│  Jobs: lint → format → type-check → unit-tests → int-tests  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (On merge to main)
┌─────────────────────────────────────────────────────────────┐
│                 Deploy Staging Workflow                      │
│  Trigger: push to main                                      │
│  Jobs: build-and-push → deploy-staging → notify             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (Manual trigger)
┌─────────────────────────────────────────────────────────────┐
│                Deploy Production Workflow                    │
│  Trigger: workflow_dispatch (manual)                        │
│  Environment: production (requires approval)                │
│  Jobs: deploy-production → smoke-tests → notify             │
└─────────────────────────────────────────────────────────────┘
```

### GitHub Actions Secrets

| Secret Name | Purpose | Source |
|-------------|---------|--------|
| AWS_ACCESS_KEY_ID | AWS API authentication | Story 0.1 CI/CD IAM user |
| AWS_SECRET_ACCESS_KEY | AWS API authentication | Story 0.1 CI/CD IAM user |
| AWS_REGION | AWS region | us-east-1 |
| KUBECONFIG_BASE64 | Kubernetes access | Story 0.3 kubeconfig |
| ECR_REGISTRY | Container registry URL | Story 0.6 ECR URL |
| SLACK_WEBHOOK_URL | Notifications (optional) | Slack app configuration |

### Workflow Permissions Matrix

| Workflow | contents | pull-requests | packages | id-token |
|----------|----------|---------------|----------|----------|
| pr-checks | read | write | read | none |
| deploy-staging | read | none | write | write |
| deploy-production | read | none | write | write |

### Reusable Workflow Inputs

**reusable-build.yml:**
```yaml
inputs:
  service_name:
    required: true
    type: string
  dockerfile_path:
    required: false
    type: string
    default: './Dockerfile'
outputs:
  image_tag:
    description: 'The pushed image tag'
```

**reusable-deploy.yml:**
```yaml
inputs:
  environment:
    required: true
    type: string
  image_tag:
    required: true
    type: string
  namespace:
    required: true
    type: string
```

### PR Checks Workflow Structure

```yaml
name: PR Checks
on:
  pull_request:
    branches: [main]

permissions:
  contents: read
  pull-requests: write

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run linter
        run: npm run lint

  test:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: npm test -- --coverage
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Project Structure Notes

```
.github/
├── workflows/
│   ├── pr-checks.yml              # PR validation workflow
│   ├── deploy-staging.yml         # Staging auto-deployment
│   ├── deploy-production.yml      # Production manual deployment
│   ├── reusable-build.yml         # Reusable Docker build
│   ├── reusable-test.yml          # Reusable test execution
│   └── reusable-deploy.yml        # Reusable K8s deployment
├── CODEOWNERS                     # Require approval for workflow changes
└── dependabot.yml                 # Keep actions up to date
```

### CODEOWNERS for Workflow Protection

```
# .github/CODEOWNERS
/.github/workflows/ @devops-lead @tech-lead
```

### Dependencies

- **Story 0.1** (Cloud Account & IAM Setup) - REQUIRED: CI/CD IAM credentials
- **Story 0.3** (Kubernetes Cluster) - REQUIRED: kubeconfig for deployments
- **Story 0.6** (Container Registry) - REQUIRED: ECR URL for image push
- Outputs used by subsequent stories:
  - Story 0.9 (Docker Build): Workflow calls reusable-build
  - Story 0.10 (Automated Tests): Workflow calls reusable-test
  - Story 0.11 (Staging Deployment): deploy-staging workflow
  - Story 0.12 (Production Deployment): deploy-production workflow

### Security Considerations

From Red Team Analysis:

1. **Threat: Workflow injection** → Mitigated by least-privilege permissions (AC7)
2. **Threat: Unauthorized workflow changes** → Mitigated by CODEOWNERS approval (AC8)
3. **Threat: Secret exposure in logs** → Mitigated by GitHub secret masking
4. **Threat: Unreviewed production deploys** → Mitigated by environment protection (AC9)

### Cost Estimate

| Component | Configuration | Monthly Cost |
|-----------|--------------|--------------|
| GitHub Actions | Team plan included minutes | $0 (included) |
| Self-hosted runners | Optional, if needed | ~$50-100/month |
| **Total** | | $0 - $100/month |

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#CI-CD-Pipeline-Sequence]
- [Source: docs/tech-specs/tech-spec-epic-0.md#GitHub-Workflow-Security]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.8]
- [Source: docs/architecture/architecture.md#CI-CD-Architecture]

## Dev Agent Record

### Context Reference

- [docs/stories/0-8-github-actions-workflow-setup.context.xml](./0-8-github-actions-workflow-setup.context.xml)

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
