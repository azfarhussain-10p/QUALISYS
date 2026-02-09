# QUALISYS Azure Infrastructure

This directory contains the complete Azure Terraform configuration for QUALISYS.

## Architecture

The configuration uses Terraform modules composed from a single root `main.tf`.
Each module encapsulates one Azure service and exposes outputs consumed by other modules.

## Directory Structure

```
azure/
├── providers.tf          # AzureRM ~3.0, AzureAD ~2.0, random, tls
├── backend.tf            # Azure Storage Account remote state
├── main.tf               # Root module composition
├── variables.tf          # Input variables
├── outputs.tf            # Unified output interface
└── modules/
    ├── resource-group/   # Resource group, tags, naming
    ├── vnet/             # VNet, subnets, NSGs, NAT Gateway, private DNS
    ├── aks/              # AKS cluster, node pools, Workload Identity
    ├── postgresql/       # PostgreSQL Flexible Server, HA, pgvector
    ├── redis/            # Azure Cache for Redis, TLS, clustering
    ├── acr/              # Container Registry, scanning, AKS pull access
    ├── keyvault/         # Key Vault, secrets (JWT, LLM, OAuth, email)
    ├── identity/         # Azure AD groups, Managed Identities, RBAC
    └── monitoring/       # Log Analytics, Activity Log, budget alerts
```

## Prerequisites

- Azure CLI configured (`az login`)
- Terraform >= 1.5.0
- An Azure subscription with Owner or Contributor permissions
- Azure AD permissions for creating groups and app registrations

## Usage

### 1. Bootstrap State Backend

Create the Azure Storage Account for Terraform state:

```bash
az group create --name qualisys-tfstate-rg --location eastus
az storage account create \
  --name qualisystfstate \
  --resource-group qualisys-tfstate-rg \
  --sku Standard_LRS \
  --encryption-services blob
az storage container create \
  --name tfstate \
  --account-name qualisystfstate
```

### 2. Deploy Infrastructure

```bash
terraform init
terraform apply \
  -var azure_subscription_id="YOUR_SUBSCRIPTION_ID" \
  -var budget_alert_email="team@example.com"
```

### 3. Environment-Specific Deployment

```bash
# Development
terraform apply \
  -var environment=dev \
  -var azure_subscription_id="..." \
  -var budget_alert_email="team@example.com"

# Production
terraform apply \
  -var environment=production \
  -var azure_subscription_id="..." \
  -var budget_alert_email="team@example.com"
```

## AWS to Azure Service Mapping

| AWS Service | Azure Equivalent |
|---|---|
| EKS | AKS (Azure Kubernetes Service) |
| RDS PostgreSQL | Azure Database for PostgreSQL Flexible Server |
| ElastiCache Redis | Azure Cache for Redis |
| ECR | ACR (Azure Container Registry) |
| S3 (state) | Azure Storage Account |
| DynamoDB (lock) | Azure Storage Table |
| Secrets Manager | Azure Key Vault |
| IAM Roles + IRSA | Azure AD + Managed Identities + Workload Identity |
| VPC + Subnets | VNet + Subnets |
| Security Groups | Network Security Groups (NSGs) |
| ALB | Azure Application Gateway |
| CloudWatch | Azure Monitor + Log Analytics |
| CloudTrail | Azure Activity Log |
| SNS | Azure Monitor Action Groups |
| Budgets | Azure Cost Management |

## Key Outputs

- AKS cluster details (name, endpoint, kubeconfig)
- PostgreSQL FQDN and connection string (via Key Vault)
- Redis hostname and access key (via Key Vault)
- ACR login server URL
- Key Vault URI
- Log Analytics workspace ID
