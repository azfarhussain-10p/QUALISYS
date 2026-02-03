# ECR Lifecycle Policy
# Story: 0-6 Container Registry
# AC: 4 - Keep last 10 tagged images
# AC: 5 - Delete untagged images after 7 days
# Tasks 3.1-3.4

resource "aws_ecr_lifecycle_policy" "repos" {
  for_each = aws_ecr_repository.repos

  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        # Task 3.3 - Keep production images indefinitely
        # Priority 1: Images matching "production-*" are claimed first,
        # preventing expiration by subsequent rules.
        rulePriority = 1
        description  = "Keep production images indefinitely"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["production-"]
          countType     = "imageCountMoreThan"
          countNumber   = 9999
        }
        action = {
          type = "expire"
        }
      },
      {
        # Task 3.1 - Keep last N tagged images (AC4)
        # Priority 2: Applies to all remaining tagged images
        # (production-* already claimed by rule 1).
        rulePriority = 2
        description  = "Keep last ${var.ecr_lifecycle_tagged_count} tagged images"
        selection = {
          tagStatus   = "tagged"
          tagPrefixList = [""]
          countType   = "imageCountMoreThan"
          countNumber = var.ecr_lifecycle_tagged_count
        }
        action = {
          type = "expire"
        }
      },
      {
        # Task 3.2 - Delete untagged images after N days (AC5)
        rulePriority = 3
        description  = "Delete untagged images after ${var.ecr_lifecycle_untagged_days} days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = var.ecr_lifecycle_untagged_days
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
