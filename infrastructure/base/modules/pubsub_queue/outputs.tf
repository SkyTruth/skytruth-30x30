output "topic_name" {
  description = "Name of the Pub/Sub topic."
  value       = google_pubsub_topic.this.name
}

output "subscription_name" {
  description = "Name of the Pub/Sub subscription."
  value       = google_pubsub_subscription.this.name
}

output "topic_id" {
  description = "ID of the Pub/Sub topic."
  value       = google_pubsub_topic.this.id
}

output "subscription_id" {
  description = "ID of the Pub/Sub subscription."
  value       = google_pubsub_subscription.this.id
}

variable "enable_message_ordering" {
  description = "Whether to enable ordered message delivery for the subscription."
  type        = bool
  default     = true
}