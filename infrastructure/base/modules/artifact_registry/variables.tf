variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "repository_id" {
  type        = string
  description = "Artifact Registry repository name (e.g. data-pipelines)"
}

variable "description" {
  type    = string
  default = "Docker images"
}
