variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "job_name" {
  type = string
}

variable "image" {
  type        = string
  description = "Full container image URI in Artifact Registry (immutable tag preferred)"
}

variable "service_account_name" {
  type        = string
  default     = null
  description = "Optional. If null, module will create one."
}

variable "timeout_seconds" {
  type    = number
  default = 7200 # 2 hours
}

variable "cpu" {
  type    = string
  default = "1"
}

variable "memory" {
  type    = string
  default = "2Gi"
}

variable "task_count" {
  type    = number
  default = 1
}

variable "max_retries" {
  type    = number
  default = 0
}

variable "env" {
  type        = map(string)
  default     = {}
  description = "Environment variables for the job container"
}

variable "additional_sa_roles" {
  type        = list(string)
  default     = []
  description = "Extra project-level IAM roles to grant the job SA (e.g., roles/storage.objectCreator)"
}


variable "secrets" {
  type = list(object({
    key        = string
    project_id = string
    secret     = string
    version    = string
  }))
  description = "List of secrets to make available to the container"
  default     = []
}