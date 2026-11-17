output "bucket_url" {
  value = google_storage_bucket.uploads.url
}

output "bucket_name" {
  value = google_storage_bucket.uploads.name
}

output "db_ip_address" {
  value = google_sql_database_instance.postgres.private_ip_address
}

output "pubsub_topic_id" {
  value = google_pubsub_topic.gcs_events.id
}

output "pubsub_subscription_name" {
  value = google_pubsub_subscription.gcs_events_sub.name
}

output "pubsub_dlq_topic_id" {
  value = google_pubsub_topic.gcs_events_dlq.id
}
