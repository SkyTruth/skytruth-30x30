resource "google_monitoring_uptime_check_config" "https" {
  display_name = "${var.name} uptime check"
  timeout      = "60s"
  period       = var.period

  http_check {
    path         = var.path
    port         = "443"
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = var.host
    }
  }
}

resource "google_monitoring_alert_policy" "alert_policy" {
  display_name = "${var.name} alert policy"
  combiner     = "OR"
  conditions {
    display_name = "test condition"

    condition_threshold {
      filter          = format("metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.label.\"check_id\"=\"%s\" AND resource.type=\"uptime_url\"", google_monitoring_uptime_check_config.https.uptime_check_id)
      duration        = "300s"
      comparison      = "COMPARISON_LT"
      threshold_value = "1"

      trigger {
        count = 1
      }
    }
  }

  notification_channels = var.notification_channels
}
