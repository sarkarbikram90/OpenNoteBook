variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Cloud Run & GCS region"
  type        = string
  default     = "asia-southeast1"
}

variable "gcs_bucket_name" {
  description = "Private GCS bucket for raw & processed OpenNotebook sources"
  type        = string
}

variable "pubsub_topic_name" {
  description = "Pub/Sub topic receiving GCS OBJECT_FINALIZE notifications"
  type        = string
  default     = "opennotebook-gcs-events"
}

variable "pubsub_verification_token" {
  description = "Secret token appended to the Pub/Sub push webhook URL"
  type        = string
  sensitive   = true
}

variable "cors_origins" {
  description = "Allowed origins for direct V4 signed browser uploads to GCS"
  type        = list(string)
  default     = ["*"]
}

variable "vector_store_provider" {
  description = "Vector store backend (pgvector or qdrant)"
  type        = string
  default     = "pgvector"
}

variable "api_image" {
  description = "Container image URI for opennotebook-api"
  type        = string
}

variable "worker_image" {
  description = "Container image URI for opennotebook-worker"
  type        = string
}

variable "frontend_image" {
  description = "Container image URI for opennotebook-frontend"
  type        = string
}

variable "api_min_instances" {
  type    = number
  default = 1
}

variable "api_max_instances" {
  type    = number
  default = 10
}

variable "worker_max_instances" {
  type    = number
  default = 5
}
