variable "topic_name" {
  description = "Name of the Pub/Sub topic."
  type        = string
}

variable "subscription_name" {
  description = "Name of the Pub/Sub subscription."
  type        = string
}

variable "labels" {
  description = "Labels to apply to the topic."
  type        = map(string)
  default     = {}
}

variable "message_retention_duration" {
  description = "How long to retain unacknowledged messages on the topic (e.g., '604800s' = 7 days)."
  type        = string
  default     = "604800s"
}

variable "subscription_retention_duration" {
  description = "How long to retain acknowledged messages on the subscription."
  type        = string
  default     = "604800s"
}

variable "ack_deadline_seconds" {
  description = "The time (in seconds) that the subscriber has to acknowledge messages."
  type        = number
  default     = 600
}

variable "retain_acked_messages" {
  description = "Whether to retain acknowledged messages for replay/debugging."
  type        = bool
  default     = false
}

variable "push_endpoint" {
  description = "Optional URL for push delivery (e.g., a Cloud Run service URL). If null, defaults to pull subscription."
  type        = string
  default     = null
}

variable "push_service_account_email" {
  description = "Service account email for authenticating push requests."
  type        = string
  default     = null
}

variable "enable_dlq" {
  type    = bool
  default = false
}

variable "max_delivery_attempts" {
  type    = number
  default = 5
}

variable "function_name" {
  type        = string
  description = "(Required) A user-defined name of the function. Function names must be unique globally."
}