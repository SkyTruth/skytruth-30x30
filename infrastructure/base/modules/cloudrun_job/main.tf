locals {
  sa_account_id = coalesce(var.service_account_name, "${var.job_name}-sa")
}

resource "google_service_account" "job_sa" {
  account_id   = local.sa_account_id
  display_name = "SA for Cloud Run Job ${var.job_name}"
}

# Optional: grant the job SA extra roles (GCS, BigQuery, etc.)
resource "google_project_iam_member" "job_sa_extra_roles" {
  for_each = toset(var.additional_sa_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.job_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "secret_access" {
  for_each = {
    for s in var.secrets : s.secret => s
  }

  secret_id = "projects/${var.project_id}/secrets/${each.value.secret}"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.job_sa.email}"
}

resource "google_cloud_run_v2_job" "default" {
  name     = var.job_name
  location = var.region

  template {
    task_count = var.task_count

    template {
      timeout     = "${var.timeout_seconds}s"
      max_retries = var.max_retries

      service_account = google_service_account.job_sa.email

      containers {
        image = var.image

        resources {
          limits = {
            cpu    = var.cpu
            memory = var.memory
          }
        }

        dynamic "env" {
          for_each = var.env
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }

  # Don't replace image if one exists
  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image
    ]
  }
}
