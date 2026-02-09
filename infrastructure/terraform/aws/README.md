# QUALISYS AWS Infrastructure

This directory contains the complete AWS Terraform configuration for QUALISYS.

## Architecture

The configuration uses a flat Terraform layout where all `.tf` files across subdirectories
are processed together as a single root configuration. Resources in one subdirectory
(e.g., `vpc/`) can be directly referenced by resources in another (e.g., `eks/`).

## Directory Structure

```
aws/
├── providers.tf          # AWS provider v5.0, random, tls
├── backend.tf            # S3 + DynamoDB remote state
├── variables.tf          # Root-level variables
├── outputs.tf            # Root-level outputs (IAM roles, SNS topics)
├── account.tf            # AWS account alias, Cost Explorer
├── vpc/                  # VPC, subnets, IGW, NAT, security groups, NACLs, flow logs
├── eks/                  # EKS cluster, node groups, OIDC, IRSA roles, addons
├── rds/                  # PostgreSQL RDS, parameter groups, secrets, KMS
├── elasticache/          # Redis cluster, parameter groups, secrets, KMS
├── ecr/                  # Container registries, lifecycle policies
├── secrets/              # Secrets Manager, KMS, rotation, ExternalSecrets IRSA
├── iam/                  # IAM roles (DevOps, Developer, CI/CD), policies, MFA
├── monitoring/           # CloudTrail, budget alerts, cost anomaly detection
├── bootstrap/            # State backend initialization (S3 + DynamoDB)
└── environments/         # Environment-specific tfvars
```

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.5.0
- An AWS account with permissions to create all resources

## Usage

### 1. Bootstrap State Backend

```bash
cd bootstrap
terraform init
terraform apply
```

### 2. Deploy Infrastructure

```bash
cd ..  # Back to aws/
terraform init
terraform apply -var-file=environments/dev.tfvars.example
```

### 3. Environment-Specific Deployment

```bash
# Development
terraform apply -var-file=environments/dev.tfvars.example

# Staging
terraform apply -var environment=staging -var budget_alert_email=team@example.com

# Production
terraform apply -var environment=production -var budget_alert_email=team@example.com
```

## Key Outputs

- IAM Role ARNs (DevOps, Developer, CI/CD, service accounts)
- EKS cluster details (endpoint, name, OIDC provider)
- RDS connection details (endpoint, secrets ARN)
- Redis connection details (configuration endpoint, secrets ARN)
- ECR repository URLs
- CloudTrail bucket name
- Budget SNS topic ARN

## AWS Services Used

| Service | Purpose |
|---|---|
| EKS | Kubernetes cluster |
| RDS PostgreSQL | Primary database |
| ElastiCache Redis | Caching, sessions, rate limiting |
| ECR | Container image registry |
| Secrets Manager | Secret storage |
| KMS | Encryption key management |
| IAM | Identity and access management |
| VPC | Network isolation |
| CloudTrail | Audit logging |
| CloudWatch | Monitoring and logging |
| SNS | Alert notifications |
| S3 | State backend, CloudTrail logs |
| DynamoDB | State locking |
