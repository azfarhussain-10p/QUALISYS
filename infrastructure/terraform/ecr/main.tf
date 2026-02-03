# ECR Repository Definitions
# Story: 0-6 Container Registry
# AC: 1 - AWS ECR container registry created
# AC: 2 - Repositories: qualisys-api, qualisys-web, playwright-runner
# AC: 3 - Image scanning enabled (scan on push)
# AC: 8 - No public access (ECR private repos deny by default)
# AC: 9 - Image tag immutability enabled
# AC: 10 - Scan results accessible via CLI/Console

# =============================================================================
# ECR Repositories (Tasks 1.1-1.6, 2.1-2.2)
# =============================================================================

resource "aws_ecr_repository" "repos" {
  for_each = var.ecr_repositories

  name = each.key

  # Task 1.4 - Image tag immutability (AC9)
  image_tag_mutability = var.ecr_image_tag_mutability

  # Task 2.1 - Scan on push (AC3, AC10)
  image_scanning_configuration {
    scan_on_push = true
  }

  # Task 1.5 - Encryption at rest using AWS-managed key (AES-256)
  encryption_configuration {
    encryption_type = "AES256"
  }

  # Task 1.6 / AC8 - ECR private repositories deny public access by default.
  # No explicit repository policy needed — IAM authentication is required for
  # all operations. Cross-account access is not possible without a repository
  # policy granting it.

  force_delete = false

  tags = {
    Name        = each.key
    Description = each.value.description
  }
}
