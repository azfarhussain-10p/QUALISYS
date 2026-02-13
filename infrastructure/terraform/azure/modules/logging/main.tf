# Azure Log Analytics for QUALISYS Logging
# Story: 0-20 Log Aggregation
# AC: 1 - Log aggregation system deployed (Azure Monitor Logs)
# AC: 7 - Log retention: 30 days staging, 90 days production

# =============================================================================
# Log Analytics Workspaces (AC1, AC7) — Tasks 1.1-1.5
# =============================================================================

resource "azurerm_log_analytics_workspace" "staging" {
  name                = "${var.project_name}-staging-logs"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = merge(var.tags, {
    Environment = "staging"
    Service     = "logging"
  })
}

resource "azurerm_log_analytics_workspace" "production" {
  name                = "${var.project_name}-production-logs"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 90

  tags = merge(var.tags, {
    Environment = "production"
    Service     = "logging"
  })
}

# =============================================================================
# Customer-Managed Key encryption (Task 1.6)
# =============================================================================

resource "azurerm_log_analytics_cluster" "logs" {
  count               = var.enable_cmk ? 1 : 0
  name                = "${var.project_name}-logs-cluster"
  location            = var.location
  resource_group_name = var.resource_group_name
  size_gb             = 500

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azurerm_log_analytics_cluster_customer_managed_key" "logs" {
  count              = var.enable_cmk ? 1 : 0
  log_analytics_cluster_id = azurerm_log_analytics_cluster.logs[0].id
  key_vault_key_id   = var.cmk_key_vault_key_id
}

# =============================================================================
# Container Insights Solutions
# =============================================================================

resource "azurerm_log_analytics_solution" "containers_staging" {
  solution_name         = "ContainerInsights"
  location              = var.location
  resource_group_name   = var.resource_group_name
  workspace_resource_id = azurerm_log_analytics_workspace.staging.id
  workspace_name        = azurerm_log_analytics_workspace.staging.name

  plan {
    publisher = "Microsoft"
    product   = "OMSGallery/ContainerInsights"
  }

  tags = var.tags
}

resource "azurerm_log_analytics_solution" "containers_production" {
  solution_name         = "ContainerInsights"
  location              = var.location
  resource_group_name   = var.resource_group_name
  workspace_resource_id = azurerm_log_analytics_workspace.production.id
  workspace_name        = azurerm_log_analytics_workspace.production.name

  plan {
    publisher = "Microsoft"
    product   = "OMSGallery/ContainerInsights"
  }

  tags = var.tags
}

# =============================================================================
# Action Group for Alerts (Task 5.5) — mirrors AWS SNS
# =============================================================================

resource "azurerm_monitor_action_group" "log_alerts" {
  name                = "${var.project_name}-log-alerts"
  resource_group_name = var.resource_group_name
  short_name          = "LogAlerts"

  dynamic "email_receiver" {
    for_each = var.alert_email != "" ? [1] : []
    content {
      name          = "log-alerts-email"
      email_address = var.alert_email
    }
  }

  dynamic "webhook_receiver" {
    for_each = var.slack_webhook_url != "" ? [1] : []
    content {
      name = "slack-webhook"
      service_uri = var.slack_webhook_url
    }
  }

  tags = var.tags
}

# =============================================================================
# AC9: Error rate spike alert (>10 errors/min) — Tasks 5.1, 5.2
# =============================================================================

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "error_rate_spike" {
  name                = "${var.project_name}-error-rate-spike"
  location            = var.location
  resource_group_name = var.resource_group_name
  description         = "Error rate exceeds 10 errors per minute (AC9)"
  severity            = 0

  scopes              = [azurerm_log_analytics_workspace.production.id]
  evaluation_frequency = "PT1M"
  window_duration      = "PT1M"

  criteria {
    query = <<-KQL
      ContainerLog
      | where LogEntry has '"level":"error"'
      | where _ResourceId has "qualisys"
      | summarize ErrorCount = count() by bin(TimeGenerated, 1m)
    KQL

    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 10

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.log_alerts.id]
  }

  tags = merge(var.tags, {
    Severity = "critical"
  })
}

# =============================================================================
# AC10: 5xx response rate >5% — Tasks 5.3, 5.4
# =============================================================================

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "high_5xx_rate" {
  name                = "${var.project_name}-high-5xx-rate"
  location            = var.location
  resource_group_name = var.resource_group_name
  description         = "5xx error rate exceeds 5% (AC10)"
  severity            = 0

  scopes              = [azurerm_log_analytics_workspace.production.id]
  evaluation_frequency = "PT1M"
  window_duration      = "PT5M"

  criteria {
    query = <<-KQL
      ContainerLog
      | where LogEntry has '"status":'
      | where _ResourceId has "qualisys"
      | extend status = toint(extract('"status":(\\d+)', 1, LogEntry))
      | summarize Total = count(), Errors5xx = countif(status >= 500) by bin(TimeGenerated, 5m)
      | where Total > 0
      | extend ErrorRate = (Errors5xx * 100.0) / Total
      | where ErrorRate > 5
    KQL

    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 5
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.log_alerts.id]
  }

  tags = merge(var.tags, {
    Severity = "critical"
  })
}

# =============================================================================
# RBAC Role Assignment for Log Access (Task 6.1)
# =============================================================================

resource "azurerm_role_assignment" "log_reader_staging" {
  count                = var.log_reader_principal_id != "" ? 1 : 0
  scope                = azurerm_log_analytics_workspace.staging.id
  role_definition_name = "Log Analytics Reader"
  principal_id         = var.log_reader_principal_id
}

resource "azurerm_role_assignment" "log_reader_production" {
  count                = var.log_reader_principal_id != "" ? 1 : 0
  scope                = azurerm_log_analytics_workspace.production.id
  role_definition_name = "Log Analytics Reader"
  principal_id         = var.log_reader_principal_id
}

# =============================================================================
# Workload Identity for Fluent Bit (Task 2.4)
# =============================================================================

resource "azurerm_user_assigned_identity" "fluent_bit" {
  name                = "${var.project_name}-fluent-bit"
  location            = var.location
  resource_group_name = var.resource_group_name

  tags = var.tags
}

resource "azurerm_federated_identity_credential" "fluent_bit" {
  name                = "${var.project_name}-fluent-bit"
  resource_group_name = var.resource_group_name
  parent_id           = azurerm_user_assigned_identity.fluent_bit.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = var.aks_oidc_issuer_url
  subject             = "system:serviceaccount:monitoring:fluent-bit"
}

resource "azurerm_role_assignment" "fluent_bit_log_contributor_staging" {
  scope                = azurerm_log_analytics_workspace.staging.id
  role_definition_name = "Log Analytics Contributor"
  principal_id         = azurerm_user_assigned_identity.fluent_bit.principal_id
}

resource "azurerm_role_assignment" "fluent_bit_log_contributor_production" {
  scope                = azurerm_log_analytics_workspace.production.id
  role_definition_name = "Log Analytics Contributor"
  principal_id         = azurerm_user_assigned_identity.fluent_bit.principal_id
}
