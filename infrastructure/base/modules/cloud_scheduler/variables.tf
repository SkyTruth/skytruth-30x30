variable "name" {
  type        = string
  description = "The name of the Cloud Scheduler job."
}

variable "description" {
  type        = string
  description = "An optional description of the job."
  default     = ""
}

variable "schedule" {
  type        = string
  description = "The cron-formatted schedule for the job"
}

variable "time_zone" {
  type        = string
  description = "The time zone to use for the schedule. Defaults to U.S. Eastern (accounts for DST)."
  default     = "America/New_York"
}

variable "target_url" {
  type        = string
  description = "The full HTTPS URL of the Cloud Run service to trigger."
}

variable "invoker_service_account" {
  type        = string
  description = "The email address of the service account used for OIDC authentication when invoking the target URL."
}

variable "headers" {
  type        = map(string)
  description = "Optional HTTP headers to send with the request."
  default     = {}
}

variable "body" {
  type        = string
  description = "Optional request body to send. Must be a JSON string or similar. Will be base64-encoded automatically."
  default     = null
}
