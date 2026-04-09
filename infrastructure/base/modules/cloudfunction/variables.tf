variable "region" {
  type        = string
  description = "GCP region"
}

variable "project" {
  type        = string
  description = "GCP project id"
}

variable "bucket_location" {
  type        = string
  description = "(Required) The GCS location."
  default     = "US"
}

variable "function_name" {
  type        = string
  description = "(Required) A user-defined name of the function. Function names must be unique globally."
}

variable "description" {
  type        = string
  description = "(Optional) Description of the function."
}

variable "runtime" {
  type        = string
  description = "(Required) The runtime in which the function is going to run. Eg. 'nodejs16', 'python39', 'dotnet3', 'go116', 'java11', 'ruby30', 'php74', etc. Check the official doc for the up-to-date list."
}

variable "available_memory" {
  type        = string
  default     = "256M"
  description = "(Optional) The amount of memory available for a function. Defaults to 256M. Supported units are k, M, G, Mi, Gi. If no unit is supplied the value is interpreted as bytes."
}

variable "available_cpu" {
  type        = number
  default     = 1
  description = "(Optional) The number of CPUs used in a single container instance. Default value is calculated from available memory."
}

variable "max_instance_count" {
  type        = number
  default     = 1
  description = "(Optional) The limit on the maximum number of function instances that may coexist at a given time."
}

variable "min_instance_count" {
  type        = number
  default     = 0
  description = "(Optional) The limit on the minimum number of function instances that may coexist at a given time."
}

variable "max_instance_request_concurrency" {
  type        = number
  default     = 80
  description = "(Optional) The limit on the maximum number of concurrent requests with respect to each function instance."
}

variable "timeout_seconds" {
  type        = number
  default     = 120
  description = "(Optional) The function execution timeout. Execution is considered failed and can be terminated if the function is not completed at the end of the timeout period. Defaults to 60 seconds."
}

variable "entry_point" {
  type        = string
  description = "(Optional) Name of the function that will be executed when the Google Cloud Function is triggered."
}

#variable "zip_path" {
#  type = string
#  description = "Path to the zip file containing the function code"
#}

variable "source_dir" {
  type        = string
  description = "Path to source directory of the function."
}

variable "vpc_connector_name" {
  type        = string
  description = "Name of the VPC Access Connector"
}

variable "build_environment_variables" {
  type        = map(string)
  description = "Key-value pairs of env vars to make available to the container"
  default     = {}
}

variable "runtime_environment_variables" {
  type        = map(string)
  description = "Key-value pairs of env vars to make available to the container"
  default     = {}
}

variable "secrets" {
  # List of objects for the secret_environment_variables block
  # The secret_environment_variables block supports:
  # key - (Required) Name of the environment variable.
  # project_id - (Required) Project identifier (preferrably project number but can also be the project ID) of the project that contains the secret. If not set, it will be populated with the function's project assuming that the secret exists in the same project as of the function.
  # secret - (Required) Name of the secret in secret manager (not the full resource name).
  # version - (Required) Version of the secret (version number or the string 'latest'). It is recommended to use a numeric version for secret environment variables as any updates to the secret value is not reflected until new instances start.
  type = list(object({
    key        = string
    project_id = string
    secret     = string
    version    = string
  }))
  description = "List of secrets to make available to the container"
  default     = []
}