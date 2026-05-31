variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "network_name" {
  description = "VPC Network Name"
  type        = string
  default     = "opennotebook-vpc"
}
