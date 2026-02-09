# MFA Enforcement Policy
# Story: 0-1 Cloud Account & IAM Setup
# AC: 4 - MFA enforced for all human users
#
# This policy denies all actions (except MFA self-management) when MFA is not present.
# Applied to all human user roles (DevOps, Developer).

resource "aws_iam_policy" "mfa_enforcement" {
  name        = "QualisysMFAEnforcement"
  description = "Deny all actions without MFA. Users can only manage their own MFA device without MFA."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowViewAccountInfo"
        Effect = "Allow"
        Action = [
          "iam:GetAccountPasswordPolicy",
          "iam:ListVirtualMFADevices"
        ]
        Resource = "*"
      },
      {
        Sid    = "AllowManageOwnMFA"
        Effect = "Allow"
        Action = [
          "iam:CreateVirtualMFADevice",
          "iam:DeleteVirtualMFADevice",
          "iam:EnableMFADevice",
          "iam:ListMFADevices",
          "iam:ResyncMFADevice",
          "iam:DeactivateMFADevice"
        ]
        Resource = [
          "arn:aws:iam::*:mfa/$${aws:username}",
          "arn:aws:iam::*:user/$${aws:username}"
        ]
      },
      {
        Sid    = "AllowManageOwnAccessKeys"
        Effect = "Allow"
        Action = [
          "iam:CreateAccessKey",
          "iam:DeleteAccessKey",
          "iam:ListAccessKeys",
          "iam:UpdateAccessKey",
          "iam:GetAccessKeyLastUsed"
        ]
        Resource = "arn:aws:iam::*:user/$${aws:username}"
      },
      {
        Sid    = "AllowManageOwnPassword"
        Effect = "Allow"
        Action = [
          "iam:ChangePassword",
          "iam:GetUser"
        ]
        Resource = "arn:aws:iam::*:user/$${aws:username}"
      },
      {
        Sid      = "DenyAllExceptMFAManagementWithoutMFA"
        Effect   = "Deny"
        NotAction = [
          "iam:CreateVirtualMFADevice",
          "iam:EnableMFADevice",
          "iam:GetUser",
          "iam:ListMFADevices",
          "iam:ListVirtualMFADevices",
          "iam:ResyncMFADevice",
          "iam:ChangePassword",
          "iam:GetAccountPasswordPolicy",
          "sts:GetSessionToken"
        ]
        Resource = "*"
        Condition = {
          BoolIfExists = {
            "aws:MultiFactorAuthPresent" = "false"
          }
        }
      }
    ]
  })
}

# Attach MFA policy to human user groups
resource "aws_iam_group" "developers" {
  name = "QualisysDevelopers"
}

resource "aws_iam_group" "devops" {
  name = "QualisysDevOps"
}

resource "aws_iam_group_policy_attachment" "developers_mfa" {
  group      = aws_iam_group.developers.name
  policy_arn = aws_iam_policy.mfa_enforcement.arn
}

resource "aws_iam_group_policy_attachment" "devops_mfa" {
  group      = aws_iam_group.devops.name
  policy_arn = aws_iam_policy.mfa_enforcement.arn
}
