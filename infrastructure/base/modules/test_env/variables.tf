
variable "gcp_region" {
  type        = string
  description = "GCP region"
}

variable "gcp_project_id" {
  type        = string
  description = "GCP project id"
}

variable "project_name" {
  type        = string
  description = "Name of the project"
}

variable "test_function_timeout_seconds" {
  type        = number
  default     = 180
  description = "Timeout for the test function"
}


variable "test_function_available_memory" {
  type        = string
  default     = "256M"
  description = "Available memory for the test function"
}

variable "test_function_available_cpu" {
  type        = number
  default     = 1
  description = "Available cpu for the test function"
}

variable "test_function_max_instance_count" {
  type        = number
  default     = 1
  description = "Max instance count for the test function"
}

variable "test_function_max_instance_request_concurrency" {
  type        = number
  default     = 80
  description = "Max instance request concurrency for the test function"
}

variable "use_hello_world_image" {
  type        = bool
  default     = false
  description = "Use the hello-world image for the cloud run service"
}
