resource "google_cloud_tasks_queue" "default" {
  name     = var.queue_name
  location = var.location

  # Rate and concurrency limits
  rate_limits {
    max_concurrent_dispatches = var.max_concurrent_dispatches
    max_dispatches_per_second = var.max_dispatches_per_second
  }

  # Retry configuration
  retry_config {
    max_attempts       = var.max_attempts
    max_retry_duration = var.max_retry_duration
    min_backoff        = var.min_backoff
    max_backoff        = var.max_backoff
    max_doublings      = var.max_doublings
  }

  # Logging (optional)
  dynamic "stackdriver_logging_config" {
    for_each = var.enable_logging ? [1] : []
    content {
      sampling_ratio = 1.0
    }
  }
}



