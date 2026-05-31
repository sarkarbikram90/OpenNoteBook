output "bucket_url" {
  value = google_storage_bucket.uploads.url
}

output "bucket_name" {
  value = google_storage_bucket.uploads.name
}

output "db_ip_address" {
  value = google_sql_database_instance.postgres.private_ip_address
}
