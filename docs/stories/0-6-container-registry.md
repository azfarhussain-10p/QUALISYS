# Story 0.6: Container Registry

Status: ready-for-dev

## Story

As a **DevOps Engineer**,
I want to **set up a container registry with image scanning and lifecycle policies**,
so that **we can store, version, and securely manage Docker images for deployment**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | AWS ECR container registry created | `aws ecr describe-repositories` shows repositories |
| AC2 | Repositories created: qualisys-api, qualisys-web, playwright-runner | All 3 repositories exist in ECR |
| AC3 | Image scanning enabled (scan for vulnerabilities on push) | `aws ecr describe-repositories` shows scanOnPush=true |
| AC4 | Lifecycle policy configured: keep last 10 tagged images | `aws ecr get-lifecycle-policy` shows rule for tagged images |
| AC5 | Lifecycle policy configured: delete untagged images after 7 days | `aws ecr get-lifecycle-policy` shows rule for untagged images |
| AC6 | IAM policy allows CI/CD role to push images | CI/CD role can successfully push test image |
| AC7 | IAM policy allows Kubernetes nodes to pull images | K8s pods can pull images from ECR |
| AC8 | Repository policy denies public access | `aws ecr get-repository-policy` shows no public access |
| AC9 | Image tag immutability enabled for production images | `aws ecr describe-repositories` shows imageTagMutability=IMMUTABLE |
| AC10 | Registry scanning results accessible via AWS Console or CLI | `aws ecr describe-image-scan-findings` returns scan results |

## Tasks / Subtasks

- [ ] **Task 1: ECR Repository Creation** (AC: 1, 2, 8, 9)
  - [ ] 1.1 Create ECR repository: qualisys-api via Terraform
  - [ ] 1.2 Create ECR repository: qualisys-web via Terraform
  - [ ] 1.3 Create ECR repository: playwright-runner via Terraform
  - [ ] 1.4 Enable image tag immutability for all repositories
  - [ ] 1.5 Configure encryption using AWS-managed key (AES-256)
  - [ ] 1.6 Verify no public access by default

- [ ] **Task 2: Image Scanning Configuration** (AC: 3, 10)
  - [ ] 2.1 Enable scan on push for all repositories
  - [ ] 2.2 Configure enhanced scanning (if using Amazon Inspector integration)
  - [ ] 2.3 Test scan by pushing a sample image
  - [ ] 2.4 Verify scan findings accessible via CLI and Console
  - [ ] 2.5 Document scan severity levels and remediation process

- [ ] **Task 3: Lifecycle Policy Configuration** (AC: 4, 5)
  - [ ] 3.1 Create lifecycle policy rule: keep last 10 tagged images
  - [ ] 3.2 Create lifecycle policy rule: delete untagged images after 7 days
  - [ ] 3.3 Create lifecycle policy rule: keep images tagged with "production-*" indefinitely
  - [ ] 3.4 Apply lifecycle policy to all repositories
  - [ ] 3.5 Test lifecycle policy by pushing test images

- [ ] **Task 4: IAM Policy Configuration** (AC: 6, 7)
  - [ ] 4.1 Create IAM policy: ecr-push-policy for CI/CD role
  - [ ] 4.2 Attach ecr-push-policy to CI/CD IAM role from Story 0.1
  - [ ] 4.3 Create IAM policy: ecr-pull-policy for Kubernetes nodes
  - [ ] 4.4 Attach ecr-pull-policy to EKS node IAM role
  - [ ] 4.5 Test push from CI/CD context (GitHub Actions or local with role assumption)
  - [ ] 4.6 Test pull from Kubernetes pod

- [ ] **Task 5: Repository Access Policy** (AC: 8)
  - [ ] 5.1 Create repository policy denying public access
  - [ ] 5.2 Allow access only from specific AWS accounts (if multi-account)
  - [ ] 5.3 Verify cross-account access blocked (if single account)

- [ ] **Task 6: Validation & Documentation** (AC: All)
  - [ ] 6.1 Run all acceptance criteria verification commands
  - [ ] 6.2 Push sample "hello-world" image to qualisys-api repository
  - [ ] 6.3 Verify image scan completes and findings accessible
  - [ ] 6.4 Deploy test pod in K8s using ECR image
  - [ ] 6.5 Document image tagging strategy in README
  - [ ] 6.6 Document CI/CD image push workflow

## Dev Notes

### Architecture Alignment

This story implements the container registry per the architecture document:

- **Image Versioning**: Git SHA and branch-based tagging for traceability
- **Security Scanning**: Vulnerability detection before deployment
- **Lifecycle Management**: Automatic cleanup prevents storage cost explosion
- **Access Control**: Least-privilege IAM policies for CI/CD and K8s

### Technical Constraints

- **Encryption**: All images encrypted at rest using AWS-managed keys
- **Tag Immutability**: Production tags cannot be overwritten (prevents accidental overwrites)
- **Scan on Push**: Every image scanned automatically for vulnerabilities
- **No Public Access**: All repositories private, accessible only via IAM

### Image Tagging Strategy

| Tag Pattern | Purpose | Example |
|-------------|---------|---------|
| `{git-sha}` | Immutable reference to exact commit | `abc123def` |
| `{branch}-{timestamp}` | Branch builds with timestamp | `main-20260123-143022` |
| `latest` | Most recent build (dev only) | `latest` |
| `production-{version}` | Production releases | `production-v1.2.3` |
| `staging-{date}` | Staging deployments | `staging-20260123` |

### Repository Configuration

| Repository | Purpose | Scan on Push | Tag Immutability |
|------------|---------|--------------|------------------|
| qualisys-api | Backend API service | Yes | Yes |
| qualisys-web | Frontend Next.js app | Yes | Yes |
| playwright-runner | Test execution container | Yes | Yes |

### Lifecycle Policy Rules

```json
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "Keep production images indefinitely",
      "selection": {
        "tagStatus": "tagged",
        "tagPrefixList": ["production-"],
        "countType": "imageCountMoreThan",
        "countNumber": 9999
      },
      "action": { "type": "expire" }
    },
    {
      "rulePriority": 2,
      "description": "Keep last 10 tagged images",
      "selection": {
        "tagStatus": "tagged",
        "countType": "imageCountMoreThan",
        "countNumber": 10
      },
      "action": { "type": "expire" }
    },
    {
      "rulePriority": 3,
      "description": "Delete untagged images after 7 days",
      "selection": {
        "tagStatus": "untagged",
        "countType": "sinceImagePushed",
        "countUnit": "days",
        "countNumber": 7
      },
      "action": { "type": "expire" }
    }
  ]
}
```

### IAM Policies

**CI/CD Push Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "arn:aws:ecr:*:*:repository/qualisys-*"
    }
  ]
}
```

**Kubernetes Pull Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    }
  ]
}
```

### Project Structure Notes

```
infrastructure/
├── terraform/
│   ├── ecr/
│   │   ├── main.tf              # ECR repository definitions
│   │   ├── lifecycle-policy.tf  # Lifecycle policy rules
│   │   ├── iam.tf               # Push/pull IAM policies
│   │   ├── variables.tf         # ECR variables
│   │   └── outputs.tf           # Repository URLs, ARNs
│   └── ...
└── README.md                    # Image tagging strategy, CI/CD workflow
```

### Dependencies

- **Story 0.1** (Cloud Account & IAM Setup) - REQUIRED: IAM roles for CI/CD and EKS
- Outputs used by subsequent stories:
  - Story 0.8 (GitHub Actions): ECR repository URLs for image push
  - Story 0.9 (Docker Build): ECR authentication and push targets
  - Story 0.3 (K8s): Node IAM role needs ECR pull permissions

### Security Considerations

From Red Team Analysis:

1. **Threat: Malicious image injection** → Mitigated by IAM policies (only CI/CD can push)
2. **Threat: Vulnerable base images** → Mitigated by scan on push (AC3, AC10)
3. **Threat: Image tag manipulation** → Mitigated by tag immutability (AC9)
4. **Threat: Unauthorized access** → Mitigated by no public access (AC8)

### Cost Estimate

| Component | Configuration | Monthly Cost |
|-----------|--------------|--------------|
| ECR Storage | 5 GB images | ~$0.50 |
| ECR Data Transfer | 10 GB/month | ~$0.90 |
| Image Scanning | Basic (included) | $0 |
| **Total** | | ~$1.50/month |

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#Services-and-Modules]
- [Source: docs/tech-specs/tech-spec-epic-0.md#Container-Registry]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.6]
- [Source: docs/architecture/architecture.md#Container-Orchestration]

## Dev Agent Record

### Context Reference

- [docs/stories/0-6-container-registry.context.xml](./0-6-container-registry.context.xml)

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
