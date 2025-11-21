data "google_project" "project" {}

# Pub/Sub Topic
resource "google_pubsub_topic" "topic" {
  name   = var.topic_name
  labels = var.labels

  # How long to retain unacknowledged messages
  message_retention_duration = var.message_retention_duration
}

# Dead Letter Queue Topic
resource "google_pubsub_topic" "dlq" {
  count = var.enable_dlq ? 1 : 0
  name  = "${var.topic_name}-dlq"
}

resource "google_service_account" "service_account" {
  account_id   = "${var.function_name}-ps-sa"
  display_name = "${var.function_name} PubSub Service Account"
}

resource "google_pubsub_topic_iam_member" "dlq_publisher" {
  count  = var.enable_dlq ? 1 : 0
  topic  = google_pubsub_topic.dlq[0].name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "dlq_subscriber" {
  count        = var.enable_dlq ? 1 : 0
  subscription = google_pubsub_subscription.subscription.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription" "dlq_sub" {
  count = var.enable_dlq ? 1 : 0
  name  = "${var.topic_name}-dlq-sub"
  topic = google_pubsub_topic.dlq[0].name
}

# Pub/Sub Subscription
resource "google_pubsub_subscription" "subscription" {
  name  = var.subscription_name
  topic = google_pubsub_topic.topic.name

  ack_deadline_seconds       = var.ack_deadline_seconds
  retain_acked_messages      = var.retain_acked_messages
  message_retention_duration = var.subscription_retention_duration
  enable_message_ordering    = var.enable_message_ordering

  # ---------------------------
  # Dead Letter Queue (optional)
  # ---------------------------
  dynamic "dead_letter_policy" {
    for_each = var.enable_dlq ? [1] : []
    content {
      dead_letter_topic     = google_pubsub_topic.dlq[0].id
      max_delivery_attempts = var.max_delivery_attempts
    }
  }

  # ---------------------------
  # Retry Settings
  # ---------------------------
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # ---------------------------
  # Push Configuration
  # ---------------------------
  dynamic "push_config" {
    for_each = var.push_endpoint != null ? [1] : []
    content {
      push_endpoint = var.push_endpoint

      oidc_token {
        service_account_email = var.push_service_account_email
      }
    }
  }

}
