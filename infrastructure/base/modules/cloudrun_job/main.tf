locals {
  sa_account_id = coalesce(var.service_account_name, "${var.name}-sa"),
  image = var.use_hello_world_image ? "gcr.io/cloudrun/hello" : "${var.region}-docker.pkg.dev/${var.project_id}/${var.repository}/${var.name}:latest"
}

resource "google_service_account" "job_sa" {
  account_id   = local.sa_account_id
  display_name = "SA for Cloud Run Job ${var.name}"
}

# Optional: grant the job SA extra roles (GCS, BigQuery, etc.)
resource "google_project_iam_member" "job_sa_extra_roles" {
  for_each = toset(var.additional_sa_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.job_sa.email}"
}

resource "google_cloud_run_v2_job" "default" {
  name     = var.name
  location = var.region

  template {
    task_count = var.task_count

    template {
      timeout     = "${var.timeout_seconds}s"
      max_retries = var.max_retries

      service_account = google_service_account.job_sa.email

      containers {
        image = local.image

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
}
