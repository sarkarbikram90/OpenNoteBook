resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = var.location

  network    = var.network
  subnetwork = var.subnetwork

  # Delete default node pool on creation so we can use custom managed pools
  remove_default_node_pool = true
  initial_node_count       = 1

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  release_channel {
    channel = "REGULAR"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
}

# ── General CPU Node Pool ────────────────────────────────────────────────────
resource "google_container_node_pool" "cpu_nodes" {
  name       = "cpu-node-pool"
  location   = var.location
  cluster    = google_container_cluster.primary.name
  node_count = var.cpu_node_count

  node_config {
    preemptible  = false
    machine_type = "e2-standard-4"

    labels = {
      role = "general"
    }

    service_account = var.service_account
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

# ── GPU Node Pool for Ollama AI Inference ─────────────────────────────────────
resource "google_container_node_pool" "gpu_nodes" {
  count      = var.enable_gpu ? 1 : 0
  name       = "gpu-node-pool"
  location   = var.location
  cluster    = google_container_cluster.primary.name
  node_count = var.gpu_node_count

  node_config {
    preemptible  = true
    machine_type = "g2-standard-4" # g2 instances feature NVIDIA L4 GPUs

    guest_accelerator {
      type  = "nvidia-l4"
      count = 1
    }

    labels = {
      role = "ai-inference"
    }

    taint {
      key    = "nvidia.com/gpu"
      value  = "present"
      effect = "NO_SCHEDULE"
    }

    service_account = var.service_account
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}
