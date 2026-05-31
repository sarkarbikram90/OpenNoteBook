variable "location" {
  description = "GCS location (e.g. US, EU)"
  type        = string
  default     = "US"
}

variable "region" {
  description = "GCP Region for CloudSQL"
  type        = string
  default     = "us-central1"
}

variable "bucket_name" {
  description = "GCS Uploads Bucket Name"
  type        = string
}

variable "db_instance_name" {
  description = "CloudSQL Instance Name"
  type        = string
  default     = "opennotebook-postgres-db"
}

variable "private_network" {
  description = "Self-link of VPC for Private IP connection"
  type        = string
}

variable "db_name" {
  description = "SQL database name"
  type        = string
  default     = "opennotebook"
}

variable "db_user" {
  description = "SQL database username"
  type        = string
  default     = "opennotebook"
}

variable "db_password" {
  description = "SQL database password"
  type        = string
  sensitive   = true
}
