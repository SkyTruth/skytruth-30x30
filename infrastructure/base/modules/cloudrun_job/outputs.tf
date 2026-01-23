output "job_name" {
  value = google_cloud_run_v2_job.this.name
}

output "job_id" {
  value = google_cloud_run_v2_job.this.id
}

output "job_service_account_email" {
  value = google_service_account.job_sa.email
}
