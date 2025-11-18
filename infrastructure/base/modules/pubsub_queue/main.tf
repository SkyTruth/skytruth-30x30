# Pub/Sub Topic
resource "google_pubsub_topic" "topic" {
  name   = var.topic_name
  labels = var.labels

  # How long to retain unacknowledged messages
  message_retention_duration = var.message_retention_duration
}

# Pub/Sub Subscription
resource "google_pubsub_subscription" "subscription" {
  name  = var.subscription_name
  topic = google_pubsub_topic.topic.name

  ack_deadline_seconds       = var.ack_deadline_seconds
  retain_acked_messages      = var.retain_acked_messages
  message_retention_duration = var.subscription_retention_duration

  # push configuration
  dynamic "push_config" {
    for_each = var.push_endpoint != null ? [1] : []
    content {
      push_endpoint = var.push_endpoint

      oidc_token {
        service_account_email = var.push_service_account_email
      }
    }
  }

  enable_message_ordering = var.enable_message_ordering
}
