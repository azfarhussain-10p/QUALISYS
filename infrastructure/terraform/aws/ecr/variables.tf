# ECR Variables
# Story: 0-6 Container Registry

variable "ecr_repositories" {
  description = "Map of ECR repository names to create"
  type = map(object({
    description = string
  }))
  default = {
    "qualisys-api" = {
      description = "Backend API service"
    }
    "qualisys-web" = {
      description = "Frontend Next.js application"
    }
    "playwright-runner" = {
      description = "Test execution container"
    }
  }
}

variable "ecr_image_tag_mutability" {
  description = "Image tag mutability setting (MUTABLE or IMMUTABLE)"
  type        = string
  default     = "IMMUTABLE"

  validation {
    condition     = contains(["MUTABLE", "IMMUTABLE"], var.ecr_image_tag_mutability)
    error_message = "Image tag mutability must be MUTABLE or IMMUTABLE."
  }
}

variable "ecr_lifecycle_tagged_count" {
  description = "Number of tagged images to keep per repository"
  type        = number
  default     = 10
}

variable "ecr_lifecycle_untagged_days" {
  description = "Days to retain untagged images before expiration"
  type        = number
  default     = 7
}
