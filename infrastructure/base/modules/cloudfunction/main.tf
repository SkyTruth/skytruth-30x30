resource "google_project_service" "cloud_functions_api" {
  service            = "cloudfunctions.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloud_run_api" {
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloud_build_api" {
  service            = "cloudbuild.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloud_logging_api" {
  service            = "logging.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "artifact_registry_api" {
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

#
# Zip file
#
resource "random_id" "default" {
  byte_length = 8
}

data "archive_file" "default" {
  type        = "zip"
  output_path = "/tmp/function-${var.function_name}-${random_id.default.hex}.zip"
  source_dir  = var.source_dir
}

#
# Bucket for source code
#
resource "google_storage_bucket" "bucket" {
  name                        = "${var.function_name}-gcf-source"
  location                    = var.bucket_location
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_object" "object" {
  name   = "${var.function_name}-${filemd5(data.archive_file.default.output_path)}.zip"
  bucket = google_storage_bucket.bucket.name
  source = data.archive_file.default.output_path
}

#
# Service account
#
resource "google_service_account" "service_account" {
  account_id   = "${var.function_name}-cf-sa"
  display_name = "${var.function_name} Cloud Functions Service Account"
}

resource "google_secret_manager_secret_iam_member" "secret_access" {
  count = length(var.secrets)

  secret_id = var.secrets[count.index]["secret"]
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.service_account.email}"

  depends_on = [google_service_account.service_account]
}

#
# Cloud function
#
resource "google_cloudfunctions2_function" "function" {
  name        = var.function_name
  location    = var.region
  description = var.description

  build_config {
    runtime           = var.runtime
    entry_point       = var.entry_point
    docker_repository = "projects/${var.project}/locations/${var.region}/repositories/gcf-artifacts"
    source {
      storage_source {
        bucket = google_storage_bucket.bucket.name
        object = google_storage_bucket_object.object.name
      }
    }
    environment_variables = var.build_environment_variables
  }

  service_config {
    vpc_connector                    = var.vpc_connector_name
    vpc_connector_egress_settings    = "PRIVATE_RANGES_ONLY"
    max_instance_count               = var.max_instance_count
    min_instance_count               = var.min_instance_count
    max_instance_request_concurrency = var.max_instance_request_concurrency
    available_memory                 = var.available_memory
    available_cpu                    = var.available_cpu
    timeout_seconds                  = var.timeout_seconds
    environment_variables            = var.runtime_environment_variables
    dynamic "secret_environment_variables" {
      # for each secret in the list of secrets, create a secret_environment_variable
      for_each = toset(var.secrets)
      content {
        key        = secret_environment_variables.value["key"]
        project_id = secret_environment_variables.value["project_id"]
        secret     = secret_environment_variables.value["secret"]
        version    = secret_environment_variables.value["version"]
      }
    }
    service_account_email = google_service_account.service_account.email
  }
}

data "google_iam_policy" "noauth" {
  binding {
    role = "roles/run.invoker"
    members = [
      "allUsers",
    ]
  }
}

resource "google_cloud_run_service_iam_policy" "noauth" {
  location = google_cloudfunctions2_function.function.location
  project  = google_cloudfunctions2_function.function.project
  service  = google_cloudfunctions2_function.function.service_config[0].service

  policy_data = data.google_iam_policy.noauth.policy_data

  depends_on = [
    google_cloudfunctions2_function.function,
  ]
}