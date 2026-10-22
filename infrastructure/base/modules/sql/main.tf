resource "google_project_service" "sql_api" {
  service            = "sqladmin.googleapis.com"
  disable_on_destroy = false

  depends_on = [google_project_service.compute_engine_api]
}

resource "google_project_service" "compute_engine_api" {
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}

resource "random_string" "random_string" {
  length = 4
  keepers = {
    name = var.name
  }
  special = false
  upper   = false
}

locals {
  postgres_database = var.database_name
  postgres_user     = var.database_user
  postgres_password = var.database_password

}

resource "google_sql_database_instance" "db-main" {
  name             = "${var.name}-${random_string.random_string.result}"
  database_version = var.database_version
  region           = var.region
  project          = var.project_id

  settings {
    tier                        = var.sql-database-instance-tier
    edition                     = "ENTERPRISE"
    deletion_protection_enabled = true

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = var.network_id
      enable_private_path_for_google_cloud_services = true
    }

    backup_configuration {
      enabled                        = var.enable_backups
      start_time                     = "05:00"
      point_in_time_recovery_enabled = true
      location                       = "us"

      backup_retention_settings {
        retained_backups = 30
      }
    }
    disk_autoresize       = true
    disk_autoresize_limit = 64
  }
}

resource "google_sql_database" "database" {
  name     = local.postgres_database
  instance = google_sql_database_instance.db-main.name
}

resource "google_sql_user" "app-user" {
  name     = local.postgres_user
  instance = google_sql_database_instance.db-main.name
  password = local.postgres_password
}
