# ─────────────────────────────────────────────────────────────────────────────
# OpenNotebook — GCP Cloud Run + GCS Pub/Sub Event-Driven Ingestion Module
# ─────────────────────────────────────────────────────────────────────────────

resource "google_service_account" "runtime" {
  account_id   = "opennotebook-cloudrun-runtime"
  display_name = "OpenNotebook Cloud Run Runtime Service Account"
}

resource "google_storage_bucket" "sources" {
  name                        = var.gcs_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  cors {
    origin          = var.cors_origins
    method          = ["PUT", "GET", "HEAD", "OPTIONS"]
    response_header = ["Content-Type", "ETag", "x-goog-meta-sha256"]
    max_age_seconds = 3600
  }
}

resource "google_storage_bucket_iam_member" "runtime_object_admin" {
  bucket = google_storage_bucket.sources.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_pubsub_topic" "gcs_dlq" {
  name = "${var.pubsub_topic_name}-dlq"
}

resource "google_pubsub_topic" "gcs_events" {
  name = var.pubsub_topic_name
}

data "google_storage_project_service_account" "gcs_account" {}

resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  topic  = google_pubsub_topic.gcs_events.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

resource "google_storage_notification" "raw_finalize" {
  bucket             = google_storage_bucket.sources.name
  payload_format     = "JSON_API_V1"
  topic              = google_pubsub_topic.gcs_events.id
  event_types        = ["OBJECT_FINALIZE"]
  object_name_prefix = "raw/"
  depends_on         = [google_pubsub_topic_iam_member.gcs_publisher]
}

resource "google_cloud_run_v2_service" "worker" {
  name     = "opennotebook-worker"
  location = var.region

  template {
    service_account = google_service_account.runtime.email
    timeout         = "900s"

    scaling {
      min_instance_count = 0
      max_instance_count = var.worker_max_instances
    }

    containers {
      image   = var.worker_image
      command = ["uvicorn"]
      args    = ["app.worker.http_worker:app", "--host", "0.0.0.0", "--port", "8080"]

      resources {
        limits = {
          cpu    = "2"
          memory = "4Gi"
        }
      }

      env {
        name  = "APP_ENV"
        value = "production"
      }
      env {
        name  = "STORAGE_PROVIDER"
        value = "gcs"
      }
      env {
        name  = "GCS_BUCKET"
        value = google_storage_bucket.sources.name
      }
      env {
        name  = "GCS_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "VECTOR_STORE_PROVIDER"
        value = var.vector_store_provider
      }
      env {
        name  = "PUBSUB_TOPIC_NAME"
        value = google_pubsub_topic.gcs_events.name
      }
    }
  }
}

resource "google_pubsub_subscription" "worker_push" {
  name  = "${var.pubsub_topic_name}-worker-push"
  topic = google_pubsub_topic.gcs_events.id

  ack_deadline_seconds = 600

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.worker.uri}/pubsub/gcs-finalize?token=${var.pubsub_verification_token}"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.gcs_dlq.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

resource "google_cloud_run_v2_service" "api" {
  name     = "opennotebook-api"
  location = var.region

  template {
    service_account = google_service_account.runtime.email
    timeout         = "300s"

    scaling {
      min_instance_count = var.api_min_instances
      max_instance_count = var.api_max_instances
    }

    containers {
      image = var.api_image

      resources {
        cpu_idle = false
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "APP_ENV"
        value = "production"
      }
      env {
        name  = "STORAGE_PROVIDER"
        value = "gcs"
      }
      env {
        name  = "GCS_BUCKET"
        value = google_storage_bucket.sources.name
      }
      env {
        name  = "GCS_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "VECTOR_STORE_PROVIDER"
        value = var.vector_store_provider
      }
      env {
        name  = "WORKER_HTTP_URL"
        value = google_cloud_run_v2_service.worker.uri
      }
    }
  }
}

resource "google_cloud_run_v2_service" "frontend" {
  name     = "opennotebook-frontend"
  location = var.region

  template {
    scaling {
      min_instance_count = 1
      max_instance_count = 5
    }

    containers {
      image = var.frontend_image

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "BACKEND_URL"
        value = google_cloud_run_v2_service.api.uri
      }
    }
  }
}
