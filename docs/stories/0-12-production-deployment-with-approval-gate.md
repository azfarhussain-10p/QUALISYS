# Story 0.12: Production Deployment with Approval Gate

Status: ready-for-dev

## Story

As a **DevOps Lead**,
I want **production deployments to require manual approval with gradual rollout**,
so that **we maintain control over production changes and can quickly rollback if issues arise**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | Production deployment workflow requires manual trigger (not automatic) | Workflow only runs via workflow_dispatch or manual button |
| AC2 | GitHub Environment "production" configured with required reviewers | Environment settings show DevOps Lead + Tech Lead as reviewers |
| AC3 | Approval required before deployment proceeds | Deployment pauses until approval granted |
| AC4 | Deployment uses canary strategy with gradual rollout (10% → 50% → 100%) | Traffic split observed during deployment |
| AC5 | Smoke tests run post-deployment to verify critical paths | Smoke test job passes after each rollout phase |
| AC6 | Automatic rollback on failed smoke tests or health checks | Failed deployment reverts to previous version |
| AC7 | Production accessible at https://app.qualisys.io | Browser navigates to production URL successfully |
| AC8 | Deployment audit trail logged (who approved, when, what version) | GitHub Actions logs and audit trail show details |
| AC9 | Rollback procedure documented and tested | CONTRIBUTING.md includes rollback steps |
| AC10 | Production deployment time <10 minutes including rollout and smoke tests | GitHub Actions summary shows total time |

## Tasks / Subtasks

- [ ] **Task 1: Production Deployment Workflow** (AC: 1, 8, 10)
  - [ ] 1.1 Create `.github/workflows/deploy-production.yml`
  - [ ] 1.2 Configure workflow_dispatch trigger (manual only)
  - [ ] 1.3 Add input parameters (image tag, rollout percentage)
  - [ ] 1.4 Configure AWS/EKS authentication
  - [ ] 1.5 Add deployment audit logging

- [ ] **Task 2: GitHub Environment Protection** (AC: 2, 3, 8)
  - [ ] 2.1 Create "production" environment in GitHub repository settings
  - [ ] 2.2 Add required reviewers (DevOps Lead, Tech Lead)
  - [ ] 2.3 Configure deployment branches (main only)
  - [ ] 2.4 Enable wait timer (optional, 5 minutes for critical changes)
  - [ ] 2.5 Configure environment secrets for production

- [ ] **Task 3: Canary Deployment Strategy** (AC: 4, 6)
  - [ ] 3.1 Configure Kubernetes canary deployment manifests
  - [ ] 3.2 Implement traffic splitting (10% canary, 90% stable)
  - [ ] 3.3 Add gradual rollout steps (10% → 50% → 100%)
  - [ ] 3.4 Configure automatic rollback on failure
  - [ ] 3.5 Implement rollout status monitoring

- [ ] **Task 4: Smoke Tests** (AC: 5, 6)
  - [ ] 4.1 Create smoke test script for critical paths
  - [ ] 4.2 Test user login flow
  - [ ] 4.3 Test API health endpoints
  - [ ] 4.4 Test database connectivity
  - [ ] 4.5 Add smoke test step after each rollout phase

- [ ] **Task 5: Production Domain Configuration** (AC: 7)
  - [ ] 5.1 Create DNS record for app.qualisys.io
  - [ ] 5.2 Configure Ingress resource for production domain
  - [ ] 5.3 Provision production SSL certificate
  - [ ] 5.4 Configure WAF rules (optional)
  - [ ] 5.5 Test domain accessibility and SSL

- [ ] **Task 6: Rollback and Documentation** (AC: 6, 9, All)
  - [ ] 6.1 Document manual rollback procedure
  - [ ] 6.2 Test rollback with intentional failure
  - [ ] 6.3 Create rollback runbook
  - [ ] 6.4 Document approval workflow in CONTRIBUTING.md
  - [ ] 6.5 Train team on production deployment process

## Dev Notes

### Architecture Alignment

This story implements production deployment per the architecture document:

- **Controlled Releases**: Manual approval ensures human oversight for production
- **Gradual Rollout**: Canary deployment limits blast radius of issues
- **Quick Recovery**: Automatic rollback minimizes downtime from bad deploys
- **Audit Trail**: Full traceability of who deployed what and when

### Technical Constraints

- **Manual Trigger Only**: Production deploys never auto-trigger
- **Required Approval**: DevOps Lead AND Tech Lead must approve
- **Canary First**: 10% traffic to canary before full rollout
- **Smoke Tests**: Critical paths verified after each rollout phase
- **Deployment Time**: <10 minutes total including rollout and smoke tests
- **Rollback SLA**: <2 minutes to rollback on failure

### Production Deployment Workflow

```yaml
# .github/workflows/deploy-production.yml
name: Deploy to Production
on:
  workflow_dispatch:
    inputs:
      image_tag:
        description: 'Image tag to deploy (Git SHA)'
        required: true
        type: string
      skip_canary:
        description: 'Skip canary phase (emergency hotfix only)'
        required: false
        type: boolean
        default: false

permissions:
  id-token: write
  contents: read
  deployments: write

jobs:
  approve:
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Deployment approved
        run: echo "Deployment approved by ${{ github.actor }}"

  canary:
    needs: approve
    if: ${{ !inputs.skip_canary }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_PRODUCTION_ROLE_ARN }}
          aws-region: us-east-1

      - name: Update kubeconfig
        run: aws eks update-kubeconfig --name qualisys-cluster --region us-east-1

      - name: Deploy canary (10%)
        run: |
          kubectl apply -f kubernetes/production/canary-deployment.yaml
          kubectl set image deployment/qualisys-api-canary \
            qualisys-api=${{ secrets.ECR_REGISTRY }}/qualisys-api:${{ inputs.image_tag }} \
            -n production
          kubectl rollout status deployment/qualisys-api-canary -n production --timeout=120s

      - name: Run smoke tests on canary
        run: |
          ./scripts/smoke-tests.sh https://canary.app.qualisys.io

      - name: Wait for canary observation (2 min)
        run: sleep 120

  rollout-50:
    needs: canary
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_PRODUCTION_ROLE_ARN }}
          aws-region: us-east-1

      - name: Update kubeconfig
        run: aws eks update-kubeconfig --name qualisys-cluster --region us-east-1

      - name: Rollout to 50%
        run: |
          kubectl scale deployment/qualisys-api-canary --replicas=5 -n production
          kubectl scale deployment/qualisys-api-stable --replicas=5 -n production

      - name: Run smoke tests
        run: ./scripts/smoke-tests.sh https://app.qualisys.io

  rollout-100:
    needs: rollout-50
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_PRODUCTION_ROLE_ARN }}
          aws-region: us-east-1

      - name: Update kubeconfig
        run: aws eks update-kubeconfig --name qualisys-cluster --region us-east-1

      - name: Promote canary to stable
        run: |
          kubectl set image deployment/qualisys-api-stable \
            qualisys-api=${{ secrets.ECR_REGISTRY }}/qualisys-api:${{ inputs.image_tag }} \
            -n production
          kubectl rollout status deployment/qualisys-api-stable -n production --timeout=180s
          kubectl scale deployment/qualisys-api-canary --replicas=0 -n production

      - name: Final smoke tests
        run: ./scripts/smoke-tests.sh https://app.qualisys.io

      - name: Notify Slack
        uses: slackapi/slack-github-action@v1
        with:
          channel-id: ${{ secrets.SLACK_DEPLOY_CHANNEL }}
          slack-message: |
            :rocket: *Production Deployment Complete*
            • Version: `${{ inputs.image_tag }}`
            • Approved by: ${{ github.actor }}
            • URL: https://app.qualisys.io
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
```

### Canary Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Production Namespace                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────────────┐      ┌─────────────────┐              │
│   │  Stable Deploy  │      │  Canary Deploy  │              │
│   │  (v1.2.3)       │      │  (v1.2.4)       │              │
│   │  Replicas: 9    │      │  Replicas: 1    │              │
│   └────────┬────────┘      └────────┬────────┘              │
│            │                        │                        │
│            └──────────┬─────────────┘                        │
│                       │                                      │
│            ┌──────────▼──────────┐                           │
│            │   Service (LB)      │                           │
│            │   Traffic Split:    │                           │
│            │   90% → Stable      │                           │
│            │   10% → Canary      │                           │
│            └──────────┬──────────┘                           │
│                       │                                      │
└───────────────────────┼──────────────────────────────────────┘
                        │
              ┌─────────▼─────────┐
              │     Ingress       │
              │ app.qualisys.io   │
              └───────────────────┘
```

### Smoke Test Script

```bash
#!/bin/bash
# scripts/smoke-tests.sh
set -e

BASE_URL="${1:-https://app.qualisys.io}"

echo "Running smoke tests against $BASE_URL"

# Test 1: Health endpoint
echo "Testing health endpoint..."
curl -sf "$BASE_URL/api/health" | jq -e '.status == "ok"'

# Test 2: Ready endpoint
echo "Testing ready endpoint..."
curl -sf "$BASE_URL/api/ready" | jq -e '.status == "ready"'

# Test 3: Login page loads
echo "Testing login page..."
curl -sf "$BASE_URL/login" | grep -q "Sign In"

# Test 4: API responds to authenticated request (using test token)
echo "Testing API authentication..."
curl -sf -H "Authorization: Bearer $SMOKE_TEST_TOKEN" \
  "$BASE_URL/api/v1/user/me" | jq -e '.id != null'

echo "All smoke tests passed!"
```

### Rollback Procedure

```bash
# Automatic rollback (Kubernetes handles this on probe failure)

# Manual rollback - Option 1: Revert to previous deployment
kubectl rollout undo deployment/qualisys-api-stable -n production
kubectl rollout undo deployment/qualisys-web-stable -n production

# Manual rollback - Option 2: Deploy specific version
kubectl set image deployment/qualisys-api-stable \
  qualisys-api=<ECR_REGISTRY>/qualisys-api:<PREVIOUS_SHA> \
  -n production

# Verify rollback
kubectl rollout status deployment/qualisys-api-stable -n production

# Check rollout history
kubectl rollout history deployment/qualisys-api-stable -n production
```

### GitHub Environment Configuration

```
Environment: production
├── Required reviewers:
│   ├── DevOps Lead (@devops-lead)
│   └── Tech Lead (@tech-lead)
├── Wait timer: 5 minutes (optional)
├── Deployment branches: main only
└── Environment secrets:
    ├── AWS_PRODUCTION_ROLE_ARN
    ├── ECR_REGISTRY
    ├── SMOKE_TEST_TOKEN
    ├── SLACK_BOT_TOKEN
    └── SLACK_DEPLOY_CHANNEL
```

### Production Ingress Configuration

```yaml
# kubernetes/production/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: production-ingress
  namespace: production
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
spec:
  tls:
    - hosts:
        - app.qualisys.io
        - api.qualisys.io
      secretName: production-tls
  rules:
    - host: app.qualisys.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: qualisys-web-stable
                port:
                  number: 3000
    - host: api.qualisys.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: qualisys-api-stable
                port:
                  number: 3000
```

### Project Structure Notes

```
/
├── .github/
│   └── workflows/
│       └── deploy-production.yml  # Production deployment workflow
├── kubernetes/
│   └── production/
│       ├── stable-deployment.yaml # Stable production deployment
│       ├── canary-deployment.yaml # Canary deployment for rollout
│       ├── service.yaml           # Services with traffic splitting
│       ├── ingress.yaml           # Production ingress
│       └── resource-quota.yaml    # Production quotas
├── scripts/
│   └── smoke-tests.sh             # Smoke test script
└── CONTRIBUTING.md                # Updated with production deploy docs
```

### Dependencies

- **Story 0.3** (Kubernetes Cluster) - REQUIRED: EKS cluster with production namespace
- **Story 0.6** (Container Registry) - REQUIRED: ECR repository for images
- **Story 0.8** (GitHub Actions) - REQUIRED: Workflow infrastructure
- **Story 0.9** (Docker Build) - REQUIRED: Docker images to deploy
- **Story 0.11** (Staging Deployment) - REQUIRED: Staging tested first
- **Story 0.13** (Load Balancer) - REQUIRED: Ingress controller for routing
- Outputs used by subsequent stories:
  - Epic 1-5: Production deployment patterns for feature releases

### Security Considerations

1. **Threat: Unauthorized production deploy** → Required reviewers, main branch only
2. **Threat: Bad deploy impacts all users** → Canary rollout limits blast radius
3. **Threat: Credential exposure** → OIDC federation, no long-lived keys
4. **Threat: Audit trail gaps** → GitHub audit logs, deployment events
5. **Threat: Slow recovery** → Automatic rollback, documented runbook

### Deployment Checklist

```markdown
## Pre-Deployment Checklist
- [ ] Changes tested in staging environment
- [ ] Staging smoke tests passing
- [ ] Database migrations applied to staging (if any)
- [ ] No blocking incidents in progress
- [ ] On-call engineer notified

## Post-Deployment Checklist
- [ ] Smoke tests passing
- [ ] Error rate normal in monitoring
- [ ] No customer-reported issues (15 min observation)
- [ ] Deployment documented in changelog
```

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#CI-CD-Pipeline-Sequence]
- [Source: docs/tech-specs/tech-spec-epic-0.md#Reliability-Availability]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.12]
- [Source: docs/architecture/architecture.md#Deployment-Strategy]

## Dev Agent Record

### Context Reference

- [docs/stories/0-12-production-deployment-with-approval-gate.context.xml](./0-12-production-deployment-with-approval-gate.context.xml)

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
