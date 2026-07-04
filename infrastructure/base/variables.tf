variable "github_org" {
  type        = string
  description = "Github organization"
}

variable "github_project" {
  type        = string
  description = "Github project name"
}

variable "staging_project_name" {
  type        = string
  description = "Name of the staging project"
}

variable "production_project_name" {
  type        = string
  description = "Name of the production project"
}

# define GCP region
variable "gcp_region" {
  type        = string
  description = "GCP region"
}

# define GCP zone
variable "gcp_zone" {
  type        = string
  description = "GCP zone"
}

# define GCP project id
variable "gcp_project_id" {
  type        = string
  description = "GCP project id"
}

variable "domain" {
  type        = string
  description = "Base domain for the DNS zone"
}

variable "staging_subdomain" {
  type        = string
  description = "Subdomain for the staging environment"
}

variable "production_subdomain" {
  type        = string
  description = "Subdomain for the production environment"
}

variable "alert_email" {
  type        = string
  description = "Email address to which monitoring alerts should be sent"
}
