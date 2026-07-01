# Shared notification channels attached to all monitoring alert policies

resource "google_monitoring_notification_channel" "alert_email" {
  display_name = "30x30 Alerts email"
  type         = "email"
  labels = {
    email_address = var.alert_email
  }
}

data "google_monitoring_notification_channel" "slack_alerts" {
  type = "slack"
  labels = {
    channel_name = "#30x30-alerts"
  }
}

locals {
  notification_channel_ids = [
    google_monitoring_notification_channel.alert_email.id,
    data.google_monitoring_notification_channel.slack_alerts.id,
  ]
}

# Cloud Scheduler logs an ERROR entry for every failed job attempt; a single
# project-wide policy covers the schedulers of both environments.
resource "google_monitoring_alert_policy" "scheduler_failures" {
  display_name = "Cloud Scheduler job failure"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Scheduler job attempt failed"

    condition_matched_log {
      filter = "resource.type=\"cloud_scheduler_job\" AND severity>=ERROR"

      label_extractors = {
        environment = "REGEXP_EXTRACT(resource.labels.job_id, \"^(${var.staging_project_name}|${var.production_project_name})\")"
        job_id      = "EXTRACT(resource.labels.job_id)"
      }
    }
  }

  alert_strategy {
    notification_rate_limit {
      period = "300s"
    }
    auto_close = "1800s"
  }

  documentation {
    content = "Cloud Scheduler job $${log.extracted_label.job_id} failed in environment $${log.extracted_label.environment}. Check its logs in Cloud Logging for the failed attempt."
  }

  notification_channels = local.notification_channel_ids
}
