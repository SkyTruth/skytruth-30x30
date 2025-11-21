output "topic_name" {
  description = "Name of the Pub/Sub topic."
  value       = google_pubsub_topic.topic.name
}

output "subscription_name" {
  description = "Name of the Pub/Sub subscription."
  value       = google_pubsub_subscription.subscription.name
}

output "topic_id" {
  description = "ID of the Pub/Sub topic."
  value       = google_pubsub_topic.topic.id
}

output "subscription_id" {
  description = "ID of the Pub/Sub subscription."
  value       = google_pubsub_subscription.subscription.id
}