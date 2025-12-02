#########################################
# Required
#########################################

variable "queue_name" {
  description = "Name of the Cloud Tasks queue."
  type        = string
}

variable "location" {
  description = "Region for the Cloud Tasks queue (e.g., us-central1)."
  type        = string
}

#########################################
# HTTP Target Info (used in your Python code)
#########################################

variable "target_url" {
  description = "Cloud Run endpoint URL this queue will send tasks to."
  type        = string
}

variable "invoker_service_account_email" {
  description = "Service account email used for OIDC authentication when Cloud Tasks invokes Cloud Run."
  type        = string
}

#########################################
# Rate Limits (queue behavior)
#########################################

variable "max_concurrent_dispatches" {
  description = "Maximum parallel task executions allowed."
  type        = number
  default     = 1
}

variable "max_dispatches_per_second" {
  description = "Rate limit for dispatching tasks."
  type        = number
  default     = 1
}

#########################################
# Retry Configuration
#########################################

variable "max_attempts" {
  description = "Max attempts including first attempt."
  type        = number
  default     = 7
}

variable "max_retry_duration" {
  description = "Total retry window (e.g., '604800s' for 7 days)."
  type        = string
  default     = "604800s"
}

variable "min_backoff" {
  description = "Minimum wait before retry (e.g., '86400s' = 1 day)."
  type        = string
  default     = "86400s"
}

variable "max_backoff" {
  description = "Maximum wait between retries."
  type        = string
  default     = "86400s"
}

variable "max_doublings" {
  description = "Exponential backoff steps (0 disables exponential delays)."
  type        = number
  default     = 0
}

#########################################
# Logging & DLQ
#########################################

variable "enable_logging" {
  description = "Enable Stackdriver logging for all task attempts."
  type        = bool
  default     = true
}

variable "enable_dlq" {
  description = "Whether to enable a Dead Letter Queue."
  type        = bool
  default     = false
}

variable "dlq_name" {
  description = "Name of a Cloud Tasks DLQ (optional)."
  type        = string
  default     = null
}
