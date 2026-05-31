variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "location" {
  description = "Primary GKE Location/Zone"
  type        = string
  default     = "us-central1-a"
}

variable "cluster_name" {
  description = "GKE Cluster Name"
  type        = string
  default     = "opennotebook-cluster"
}

variable "network" {
  description = "VPC Network ID"
  type        = string
}

variable "subnetwork" {
  description = "Subnet ID"
  type        = string
}

variable "service_account" {
  description = "IAM Service Account email for nodes"
  type        = string
}

variable "cpu_node_count" {
  description = "Initial CPU nodes"
  type        = number
  default     = 2
}

variable "enable_gpu" {
  description = "Enable NVIDIA GPU Node Pool"
  type        = bool
  default     = true
}

variable "gpu_node_count" {
  description = "Initial GPU nodes"
  type        = number
  default     = 1
}
