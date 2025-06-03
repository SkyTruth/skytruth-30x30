variable "github_org" {
  type        = string
  description = "Github organization"
}

variable "github_project" {
  type        = string
  description = "Github project name"
}

variable "project_name" {
  type        = string
  description = "Name of the project"
}

# define GCP region
variable "gcp_region" {
  type        = string
  description = "GCP region"
}

# define GCP project id
variable "gcp_project_id" {
  type        = string
  description = "GCP project id"
}

variable "tf_state_prefix" {
  type        = string
  default     = "state"
  description = "The prefix for the TF state in the Google Storage Bucket"
}

variable "dns_zone_name" {
  type        = string
  description = "Name for the GCP DNS Zone"
}

variable "domain" {
  type        = string
  description = "Base domain for the DNS zone"
}

variable "subdomain" {
  type        = string
  default     = ""
  description = "If set, it will be prepended to the domain to form a subdomain."
}

variable "frontend_min_scale" {
  type        = number
  description = "Minimum number of frontend app instances to deploy"
  default     = 0
}

variable "frontend_max_scale" {
  type        = number
  description = "Maximum number of frontend app instances to deploy"
  default     = 5
}

variable "backend_min_scale" {
  type        = number
  description = "Minimum number of backend app instances to deploy"
  default     = 0
}

variable "backend_max_scale" {
  type        = number
  description = "Maximum number of backend app instances to deploy"
  default     = 5
}

variable "cors_origin" {
  type        = string
  description = "Origin for CORS config"
  default     = "*"
}

variable "uptime_alert_email" {
  type        = string
  description = "Email address to which uptime alerts should be sent"
}

variable "environment" {
  type        = string
  description = "staging | production"
}

variable "database_name" {
  type        = string
  description = "Name of the database"
}

variable "database_user" {
  type        = string
  description = "Name of the database user"
}

variable "backend_path_prefix" {
  type        = string
  description = "Path prefix for the backend service"
}

variable "backend_write_user" {
  type        = string
  description = "Username to authenticate the write and update endpoints in the backend service"
}

variable "functions_path_prefix" {
  type        = string
  description = "Path prefix for the functions services"
}

variable "analysis_function_path_prefix" {
  type        = string
  description = "Path prefix for the analysis function"
}

variable "analysis_function_timeout_seconds" {
  type        = number
  default     = 180
  description = "Timeout for the analysis function"
}

variable "analysis_function_available_memory" {
  type        = string
  default     = "256M"
  description = "Available memory for the analysis function"
}

variable "analysis_function_available_cpu" {
  type        = number
  default     = 1
  description = "Available cpu for the analysis function"
}

variable "analysis_function_max_instance_count" {
  type        = number
  default     = 1
  description = "Max instance count for the analysis function"
}

variable "analysis_function_max_instance_request_concurrency" {
  type        = number
  default     = 80
  description = "Max instance request concurrency for the analysis function"
}

variable "use_hello_world_image" {
  type        = bool
  default     = false
  description = "Use the hello-world image for the cloud run service"
}

variable "data_processing_timeout_seconds" {
  type        = number
  default     = 600
  description = "Timeout for the data processing function"
}

variable "data_processing_available_memory" {
  type        = string
  default     = "8G"
  description = "Available memory for the data processing function"
}

variable "data_processing_available_cpu" {
  type        = number
  default     = 2
  description = "Available cpu for the data processing function"
}

variable "data_processing_max_instance_count" {
  type        = number
  default     = 1
  description = "Max instance count for the data processing function"
}

variable "data_processing_max_instance_request_concurrency" {
  type        = number
  default     = 1
  description = "Max instance request concurrency for the data processing function"
}

variable "scheduler_invoker_sa" {
  type        = string
  default     = null
  description = "Service account used by Cloud Scheduler"
}
