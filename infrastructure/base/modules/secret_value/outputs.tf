output "secret_name" {
  value = google_secret_manager_secret.secret.secret_id

  # Consumers read the secret by name, so it must have a version first.
  depends_on = [google_secret_manager_secret_version.backend_app_secret]
}

output "secret_id" {
  value = google_secret_manager_secret.secret.id
}

output "secret_value" {
  value = google_secret_manager_secret_version.backend_app_secret.secret_data
}

output "latest_version" {
  value = data.google_secret_manager_secret_version.latest.version
}