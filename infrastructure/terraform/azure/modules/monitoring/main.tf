# Azure Monitor & Log Analytics
# QUALISYS Azure Infrastructure — mirrors AWS CloudWatch/CloudTrail/Budgets
# Log Analytics workspace, Activity Log, Cost Management alerts

# =============================================================================
# Log Analytics Workspace (mirrors CloudWatch)
# =============================================================================

resource "azurerm_log_analytics_workspace" "main" {
  name                = "${var.project_name}-${var.environment}-logs"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days

  tags = var.tags
}

# =============================================================================
# Log Analytics Solutions
# =============================================================================

resource "azurerm_log_analytics_solution" "containers" {
  solution_name         = "ContainerInsights"
  location              = var.location
  resource_group_name   = var.resource_group_name
  workspace_resource_id = azurerm_log_analytics_workspace.main.id
  workspace_name        = azurerm_log_analytics_workspace.main.name

  plan {
    publisher = "Microsoft"
    product   = "OMSGallery/ContainerInsights"
  }

  tags = var.tags
}

# =============================================================================
# Activity Log Diagnostic Setting (mirrors CloudTrail)
# =============================================================================

data "azurerm_subscription" "current" {}

resource "azurerm_monitor_diagnostic_setting" "activity_log" {
  name                       = "${var.project_name}-activity-log"
  target_resource_id         = data.azurerm_subscription.current.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category = "Administrative"
  }

  enabled_log {
    category = "Security"
  }

  enabled_log {
    category = "Alert"
  }

  enabled_log {
    category = "Policy"
  }
}

# =============================================================================
# Action Group for Alerts (mirrors SNS topic)
# =============================================================================

resource "azurerm_monitor_action_group" "budget_alerts" {
  name                = "${var.project_name}-budget-alerts"
  resource_group_name = var.resource_group_name
  short_name          = "BudgetAlert"

  email_receiver {
    name          = "budget-email"
    email_address = var.budget_alert_email
  }

  tags = var.tags
}

# =============================================================================
# Cost Management Budget Alerts (mirrors AWS Budgets)
# =============================================================================

resource "azurerm_consumption_budget_subscription" "monthly_500" {
  name            = "${var.project_name}-monthly-500"
  subscription_id = data.azurerm_subscription.current.id
  amount          = 500
  time_grain      = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Actual"

    contact_groups = [azurerm_monitor_action_group.budget_alerts.id]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Actual"

    contact_groups = [azurerm_monitor_action_group.budget_alerts.id]
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}

resource "azurerm_consumption_budget_subscription" "monthly_1000" {
  name            = "${var.project_name}-monthly-1000"
  subscription_id = data.azurerm_subscription.current.id
  amount          = 1000
  time_grain      = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Actual"

    contact_groups = [azurerm_monitor_action_group.budget_alerts.id]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Actual"

    contact_groups = [azurerm_monitor_action_group.budget_alerts.id]
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}

resource "azurerm_consumption_budget_subscription" "monthly_2000" {
  name            = "${var.project_name}-monthly-2000"
  subscription_id = data.azurerm_subscription.current.id
  amount          = 2000
  time_grain      = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Actual"

    contact_groups = [azurerm_monitor_action_group.budget_alerts.id]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Actual"

    contact_groups = [azurerm_monitor_action_group.budget_alerts.id]
  }

  # Anomaly detection at 150% forecast
  notification {
    enabled        = true
    threshold      = 150
    operator       = "GreaterThan"
    threshold_type = "Forecasted"

    contact_groups = [azurerm_monitor_action_group.budget_alerts.id]
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}
