variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "Primary GCP Region"
  type        = string
  default     = "us-central1"
}

variable "gke_zone" {
  description = "Zone for GKE cluster"
  type        = string
  default     = "us-central1-a"
}

variable "db_password" {
  description = "Password for the CloudSQL Postgres DB"
  type        = string
  sensitive   = true
}

variable "enable_gpu" {
  description = "Enable GPU Node Pool for local AI model inference"
  type        = bool
  default     = true
}
