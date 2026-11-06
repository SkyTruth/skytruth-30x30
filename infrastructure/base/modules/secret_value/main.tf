resource "random_password" "secret_value" {
  count = var.use_random_value ? 1 : 0

  length  = var.random_value_length
  special = false
}

resource "google_project_service" "secret_manager_api" {
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_secret_manager_secret" "secret" {
  secret_id = "${var.key}_secret"

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  depends_on = [google_project_service.secret_manager_api]
}

resource "google_secret_manager_secret_version" "backend_app_secret" {
  secret = google_secret_manager_secret.secret.id

  secret_data = var.use_random_value ? random_password.secret_value[0].result : var.value
}

data "google_secret_manager_secret_version" "latest" {
  secret = google_secret_manager_secret.secret.id

  # A new secret has no versions until backend_app_secret is created.
  depends_on = [google_secret_manager_secret_version.backend_app_secret]
}
