output "vpc_network_id" {
  value = module.networking.network_id
}

output "gcs_bucket_name" {
  value = module.storage.bucket_name
}

output "db_private_ip" {
  value = module.storage.db_ip_address
}

output "gke_cluster_name" {
  value = module.gke.cluster_name
}

output "gke_endpoint" {
  value = module.gke.endpoint
}
