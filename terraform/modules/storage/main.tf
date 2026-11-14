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
