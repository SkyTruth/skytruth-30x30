resource "google_cloud_scheduler_job" "job" {
  name        = var.name
  description = var.description
  schedule    = var.schedule
  time_zone   = var.time_zone

  http_target {
    uri         = var.target_url
    http_method = "POST"

    oidc_token {
      service_account_email = var.invoker_service_account
    }

    headers = var.headers
    body    = var.body != null ? base64encode(var.body) : null
  }
}
