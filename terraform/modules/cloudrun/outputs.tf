output "api_url" {
  description = "Public URL of the Cloud Run opennotebook-api service"
  value       = google_cloud_run_v2_service.api.uri
}

output "worker_url" {
  description = "URL of the Cloud Run opennotebook-worker HTTP ingestion service"
  value       = google_cloud_run_v2_service.worker.uri
}

output "frontend_url" {
  description = "Public URL of the Cloud Run opennotebook-frontend service"
  value       = google_cloud_run_v2_service.frontend.uri
}

output "gcs_bucket_name" {
  description = "Private GCS bucket configured with OBJECT_FINALIZE notifications"
  value       = google_storage_bucket.sources.name
}

output "pubsub_topic_id" {
  description = "Pub/Sub topic ID for GCS ingestion events"
  value       = google_pubsub_topic.gcs_events.id
}

output "runtime_service_account_email" {
  description = "Service account email used by Cloud Run API and worker"
  value       = google_service_account.runtime.email
}
