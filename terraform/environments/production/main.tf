terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ── Service Account for GKE Pods / Nodes ─────────────────────────────────────
resource "google_service_account" "gke_sa" {
  account_id   = "opennotebook-gke-sa"
  display_name = "OpenNotebook GKE Service Account"
}

# ── Networking Module ────────────────────────────────────────────────────────
module "networking" {
  source       = "../../modules/networking"
  region       = var.region
  network_name = "opennotebook-production-vpc"
}

# ── Storage & Databases Module ───────────────────────────────────────────────
module "storage" {
  source           = "../../modules/storage"
  location         = "US"
  region           = var.region
  bucket_name      = "opennotebook-prod-uploads-${var.project_id}"
  private_network  = module.networking.network_self_link
  db_password      = var.db_password
  depends_on       = [module.networking.private_connection_id]
}

# ── GKE Cluster Module ───────────────────────────────────────────────────────
module "gke" {
  source          = "../../modules/gke"
  project_id      = var.project_id
  location        = var.gke_zone
  cluster_name    = "opennotebook-production-gke"
  network         = module.networking.network_id
  subnetwork      = module.networking.subnet_id
  service_account = google_service_account.gke_sa.email
  enable_gpu      = var.enable_gpu
}
