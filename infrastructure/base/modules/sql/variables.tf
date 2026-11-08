variable "region" {
  type        = string
  description = "GCP region"
}

variable "project_id" {
  type        = string
  description = "GCP project id"
}

variable "name" {
  type        = string
  description = "Name of the SQL server instance"
}

variable "sql-database-instance-tier" {
  description = "Cloud SQL database instance (server) tier"
  type        = string
  default     = "db-f1-micro"
}

variable "database_version" {
  type        = string
  default     = "POSTGRES_14"
  description = "Version SQL server instance"
}

variable "network_id" {
  description = "The GCP network id in which the database will be available"
}

variable "database_name" {
  type        = string
  description = "Name of the database"
}

variable "database_user" {
  type        = string
  description = "Name of the database user"
}

variable "database_password" {
  type        = string
  description = "Password for the database user"
}

variable "read_only_user" {
  type        = string
  description = "Name of the database user granted read-only access"
}

variable "read_only_password" {
  type        = string
  description = "Password for the read-only database user"
}

variable "enable_backups" {
  type        = bool
  default     = true
  description = "If database backups should be enabled"
}
