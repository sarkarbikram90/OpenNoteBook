# ── Cloud Storage (GCS) for source file uploads ──────────────────────────────
resource "google_storage_bucket" "uploads" {
  name          = var.bucket_name
  location      = var.location
  storage_class = "STANDARD"
  # Protect source documents from accidental Terraform bucket deletion.
  force_destroy = false

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  encryption {
    customer_supplied_encryption_enforcement_config {
      restriction_mode = "FullyRestricted"
    }
    customer_managed_encryption_enforcement_config {
      restriction_mode = "NotRestricted"
    }
    google_managed_encryption_enforcement_config {
      restriction_mode = "NotRestricted"
    }
  }

  soft_delete_policy {
    retention_duration_seconds = 604800 # 7 days
  }

  lifecycle_rule {
    action {
      type = "AbortIncompleteMultipartUpload"
    }
    condition {
      age = 7
    }
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "POST", "PUT", "DELETE"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}

# ── Google Pub/Sub for GCS OBJECT_FINALIZE Event Ingestion ──────────────────
data "google_storage_project_service_account" "gcs_account" {}

resource "google_pubsub_topic" "gcs_events" {
  name = var.pubsub_topic_name
}

resource "google_pubsub_topic" "gcs_events_dlq" {
  name = "${var.pubsub_topic_name}-dlq"
}

resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  topic  = google_pubsub_topic.gcs_events.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

resource "google_storage_notification" "uploads_finalize" {
  bucket             = google_storage_bucket.uploads.name
  payload_format     = "JSON_API_V1"
  topic              = google_pubsub_topic.gcs_events.id
  event_types        = ["OBJECT_FINALIZE"]
  object_name_prefix = "raw/"
  depends_on         = [google_pubsub_topic_iam_member.gcs_publisher]
}

resource "google_pubsub_subscription" "gcs_events_sub" {
  name  = "${var.pubsub_topic_name}-sub"
  topic = google_pubsub_topic.gcs_events.name

  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"
  retain_acked_messages      = false

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.gcs_events_dlq.id
    max_delivery_attempts = 5
  }

  dynamic "push_config" {
    for_each = var.pubsub_push_endpoint != "" ? [var.pubsub_push_endpoint] : []
    content {
      push_endpoint = push_config.value
    }
  }
}

# ── CloudSQL PostgreSQL Instance ──────────────────────────────────────────────
resource "google_sql_database_instance" "postgres" {
  name             = var.db_instance_name
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier = "db-f1-micro" # Lightweight development tier, can scale for production

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.private_network
    }

    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = false
}

resource "google_sql_database" "database" {
  name     = var.db_name
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "user" {
  name     = var.db_user
  instance = google_sql_database_instance.postgres.name
  password = var.db_password
}
