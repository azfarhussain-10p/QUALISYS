# AWS Account Configuration
# Story: 0-1 Cloud Account & IAM Setup
# AC: 1 - AWS account configured
# Task 1.3 - Account alias for identification
# Task 1.4 - Cost Explorer enabled

# Account alias for easier identification (Task 1.3)
resource "aws_iam_account_alias" "qualisys" {
  account_alias = var.account_alias
}

# Enable Cost Explorer (Task 1.4)
# Note: Cost Explorer is enabled at the organization/account level.
# This can be done via AWS Console or CLI:
#   aws ce enable --no-cli-pager
# Terraform does not have a native resource for enabling Cost Explorer.
# The aws_ce_anomaly_monitor in monitoring/budgets.tf implicitly requires it.
