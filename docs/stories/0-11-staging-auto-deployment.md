# Story 0.11: Staging Auto-Deployment

Status: ready-for-dev

## Story

As a **Developer**,
I want **code merged to main to automatically deploy to staging**,
so that **we can test in a production-like environment with zero manual intervention**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | On main branch merge, workflow triggers automatic deployment to staging | GitHub Actions logs show workflow triggered on merge |
| AC2 | Deployment updates Kubernetes deployment with new image tag | kubectl get deployment shows updated image tag |
| AC3 | Rolling update strategy ensures zero-downtime deployment | Traffic continues during deployment (load test) |
| AC4 | Health checks verify deployment success (readiness/liveness probes) | Deployment status shows all pods healthy |
| AC5 | Deployment rollback on failed health checks (automatic) | Failed deployment reverts to previous version |
| AC6 | Slack notification sent on deployment (success/failure with link) | Slack channel receives notification with staging URL |
| AC7 | Staging environment accessible at https://staging.qualisys.dev | Browser navigates to staging URL successfully |
| AC8 | Deployment time <2 minutes from merge to running pods | GitHub Actions logs show total time <2 min |
| AC9 | Deployment manifest uses image from ECR with Git SHA tag | kubectl describe deployment shows ECR image:sha |
| AC10 | Staging namespace has appropriate resource limits configured | kubectl describe namespace shows resource quotas |

## Tasks / Subtasks

- [ ] **Task 1: Deploy Staging Workflow** (AC: 1, 8)
  - [ ] 1.1 Create `.github/workflows/deploy-staging.yml`
  - [ ] 1.2 Configure workflow trigger on push to main branch
  - [ ] 1.3 Add job to authenticate with AWS ECR
  - [ ] 1.4 Add job to configure kubectl with EKS cluster
  - [ ] 1.5 Optimize workflow for <2 minute execution

- [ ] **Task 2: Kubernetes Deployment Configuration** (AC: 2, 3, 9, 10)
  - [ ] 2.1 Create deployment manifests for staging namespace
  - [ ] 2.2 Configure rolling update strategy (maxUnavailable=0, maxSurge=1)
  - [ ] 2.3 Set resource requests and limits (CPU, memory)
  - [ ] 2.4 Configure image pull policy and ECR image reference
  - [ ] 2.5 Set replica count for staging (minimum 2 for HA)
  - [ ] 2.6 Configure namespace resource quotas

- [ ] **Task 3: Health Check Configuration** (AC: 4, 5)
  - [ ] 3.1 Implement /health endpoint in API service (liveness probe)
  - [ ] 3.2 Implement /ready endpoint in API service (readiness probe)
  - [ ] 3.3 Configure Kubernetes probes with appropriate timeouts
  - [ ] 3.4 Set probe failure thresholds (3 failures before unhealthy)
  - [ ] 3.5 Configure deployment rollback on probe failure

- [ ] **Task 4: Slack Notification Integration** (AC: 6)
  - [ ] 4.1 Create Slack webhook for deployment notifications
  - [ ] 4.2 Store webhook URL in GitHub Secrets
  - [ ] 4.3 Add notification step to workflow (success message)
  - [ ] 4.4 Add notification step to workflow (failure message)
  - [ ] 4.5 Include staging URL and Git SHA in notification

- [ ] **Task 5: Staging Domain Configuration** (AC: 7)
  - [ ] 5.1 Create DNS record for staging.qualisys.dev
  - [ ] 5.2 Configure Ingress resource for staging domain
  - [ ] 5.3 Provision SSL certificate (Let's Encrypt/ACM)
  - [ ] 5.4 Configure HTTPS redirect
  - [ ] 5.5 Test domain accessibility from public internet

- [ ] **Task 6: Validation & Documentation** (AC: All)
  - [ ] 6.1 Test deployment with sample PR merged to main
  - [ ] 6.2 Verify rolling update with zero downtime
  - [ ] 6.3 Test rollback scenario with failing health check
  - [ ] 6.4 Verify Slack notification received
  - [ ] 6.5 Document deployment process in CONTRIBUTING.md

## Dev Notes

### Architecture Alignment

This story implements staging auto-deployment per the architecture document:

- **Continuous Deployment**: Automated deployment on merge reduces manual errors
- **Zero-Downtime**: Rolling updates ensure availability during deployments
- **Health Monitoring**: Probes enable automatic failure detection and recovery
- **Fast Feedback**: <2 minute deployment enables rapid iteration

### Technical Constraints

- **Deployment Time**: <2 minutes from merge to running pods
- **Zero-Downtime**: Rolling update with maxUnavailable=0
- **Health Checks**: Both readiness and liveness probes required
- **Resource Limits**: Staging namespace must have quotas to prevent runaway usage
- **SSL**: HTTPS enforced for staging environment

### Deployment Workflow

```yaml
# .github/workflows/deploy-staging.yml
name: Deploy to Staging
on:
  push:
    branches: [main]

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_STAGING_ROLE_ARN }}
          aws-region: us-east-1

      - name: Login to Amazon ECR
        uses: aws-actions/amazon-ecr-login@v2

      - name: Update kubeconfig
        run: aws eks update-kubeconfig --name qualisys-cluster --region us-east-1

      - name: Deploy to staging
        run: |
          kubectl set image deployment/qualisys-api \
            qualisys-api=${{ secrets.ECR_REGISTRY }}/qualisys-api:${{ github.sha }} \
            -n staging
          kubectl set image deployment/qualisys-web \
            qualisys-web=${{ secrets.ECR_REGISTRY }}/qualisys-web:${{ github.sha }} \
            -n staging
          kubectl rollout status deployment/qualisys-api -n staging --timeout=120s
          kubectl rollout status deployment/qualisys-web -n staging --timeout=120s

      - name: Notify Slack (Success)
        if: success()
        uses: slackapi/slack-github-action@v1
        with:
          channel-id: ${{ secrets.SLACK_DEPLOY_CHANNEL }}
          slack-message: |
            :white_check_mark: *Staging Deployment Successful*
            • Commit: `${{ github.sha }}`
            • Author: ${{ github.actor }}
            • URL: https://staging.qualisys.dev
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}

      - name: Notify Slack (Failure)
        if: failure()
        uses: slackapi/slack-github-action@v1
        with:
          channel-id: ${{ secrets.SLACK_DEPLOY_CHANNEL }}
          slack-message: |
            :x: *Staging Deployment Failed*
            • Commit: `${{ github.sha }}`
            • Author: ${{ github.actor }}
            • Action: https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
```

### Kubernetes Deployment Manifest

```yaml
# kubernetes/staging/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: qualisys-api
  namespace: staging
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  selector:
    matchLabels:
      app: qualisys-api
  template:
    metadata:
      labels:
        app: qualisys-api
    spec:
      containers:
        - name: qualisys-api
          image: ${ECR_REGISTRY}/qualisys-api:${IMAGE_TAG}
          ports:
            - containerPort: 3000
          resources:
            requests:
              cpu: "100m"
              memory: "256Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
          livenessProbe:
            httpGet:
              path: /health
              port: 3000
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /ready
              port: 3000
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 3
          env:
            - name: NODE_ENV
              value: "staging"
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: qualisys-secrets
                  key: database-url
```

### Health Check Endpoints

```javascript
// API health check endpoints
// /health - liveness probe (is the process running?)
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok' });
});

// /ready - readiness probe (is the service ready to receive traffic?)
app.get('/ready', async (req, res) => {
  try {
    // Check database connection
    await db.query('SELECT 1');
    // Check Redis connection
    await redis.ping();
    res.status(200).json({ status: 'ready' });
  } catch (error) {
    res.status(503).json({ status: 'not ready', error: error.message });
  }
});
```

### Ingress Configuration

```yaml
# kubernetes/staging/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: staging-ingress
  namespace: staging
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
    - hosts:
        - staging.qualisys.dev
      secretName: staging-tls
  rules:
    - host: staging.qualisys.dev
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: qualisys-api
                port:
                  number: 3000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: qualisys-web
                port:
                  number: 3000
```

### Resource Quota for Staging

```yaml
# kubernetes/staging/resource-quota.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: staging-quota
  namespace: staging
spec:
  hard:
    requests.cpu: "2"
    requests.memory: "4Gi"
    limits.cpu: "4"
    limits.memory: "8Gi"
    pods: "20"
```

### Project Structure Notes

```
/
├── .github/
│   └── workflows/
│       └── deploy-staging.yml   # Staging auto-deployment workflow
├── kubernetes/
│   └── staging/
│       ├── deployment.yaml      # API and Web deployments
│       ├── service.yaml         # Kubernetes services
│       ├── ingress.yaml         # Ingress configuration
│       └── resource-quota.yaml  # Namespace quotas
├── api/
│   └── src/
│       └── health.ts            # Health check endpoints
└── CONTRIBUTING.md              # Updated with deployment docs
```

### Dependencies

- **Story 0.3** (Kubernetes Cluster) - REQUIRED: EKS cluster with staging namespace
- **Story 0.6** (Container Registry) - REQUIRED: ECR repository for images
- **Story 0.8** (GitHub Actions) - REQUIRED: Workflow infrastructure
- **Story 0.9** (Docker Build) - REQUIRED: Docker images to deploy
- **Story 0.13** (Load Balancer) - REQUIRED: Ingress controller for routing
- Outputs used by subsequent stories:
  - Story 0.12 (Production Deployment): Deployment patterns, health checks
  - Story 0.17 (Test Reporting): Staging environment for dashboard deployment

### Security Considerations

From Red Team Analysis:

1. **Threat: Credential exposure** → Use OIDC federation (role-to-assume), no long-lived keys
2. **Threat: Unauthorized deployment** → GitHub Environment protection rules
3. **Threat: Staging data leakage** → Staging uses separate database, test data only
4. **Threat: SSL stripping** → HTTPS redirect enforced, HSTS headers
5. **Threat: Resource exhaustion** → Resource quotas limit namespace usage

### Rollback Strategy

```bash
# Automatic rollback on failed health checks (Kubernetes handles this)

# Manual rollback if needed
kubectl rollout undo deployment/qualisys-api -n staging
kubectl rollout undo deployment/qualisys-web -n staging

# Check rollout history
kubectl rollout history deployment/qualisys-api -n staging
```

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#CI-CD-Pipeline-Sequence]
- [Source: docs/tech-specs/tech-spec-epic-0.md#Reliability-Availability]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.11]
- [Source: docs/architecture/architecture.md#Deployment-Strategy]

## Dev Agent Record

### Context Reference

- [docs/stories/0-11-staging-auto-deployment.context.xml](./0-11-staging-auto-deployment.context.xml)

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
