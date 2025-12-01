output "queue_name" {
  description = "Cloud Tasks queue name."
  value       = google_cloud_tasks_queue.default.name
}

output "queue_location" {
  description = "Cloud Tasks queue region."
  value       = google_cloud_tasks_queue.default.location
}

output "queue_id" {
  description = "Full resource ID for the queue."
  value       = google_cloud_tasks_queue.default.id
}

output "target_url" {
  description = "Cloud Run URL tasks should call."
  value       = var.target_url
}

output "invoker_service_account_email" {
  description = "Service account used for OIDC authentication."
  value       = var.invoker_service_account_email
}
