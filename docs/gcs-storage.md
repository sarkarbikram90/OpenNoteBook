# Google Cloud Storage & Event-Driven RAG Architecture for OpenNoteBook

OpenNotebook uses a private Google Cloud Storage bucket as its authoritative
object store for unstructured documents (PDFs, TXT, Markdown, DOCX, and Images)
and derived processing artifacts, integrated with Google Pub/Sub, Vertex AI
Text Embeddings, PostgreSQL + `pgvector` (or Qdrant), and Gemini / pluggable LLMs.

## System Architecture

```text
OpenNoteBook Frontend
  Upload documents · Manage notebooks · Ask questions
        │
        ▼
Backend API (FastAPI)
  Authentication · Document metadata · Signed upload URLs · Query API
        │
        ▼
Google Cloud Storage (Primary Document Repository)
  raw/{notebook_id}/{source_id}/{filename}  (PDFs · TXT · Markdown · Images)
        │
        │  OBJECT_FINALIZE event
        ▼
Google Pub/Sub (Asynchronous Event Delivery + DLQ)
  POST /api/v1/events/gcs-finalize (Idempotent by GCS object generation)
        │
        ▼
Document Processing Worker (Cloud Run / Celery)
  PDF extraction (PyMuPDF + OCR) · Text/Markdown/DOCX · Image OCR/Vision (Tesseract / Gemini Vision / Document AI)
  PII Redaction · Semantic Chunking
        │
        ▼
Embedding Generation
  Vertex AI text-embedding-004 (RETRIEVAL_DOCUMENT / RETRIEVAL_QUERY) or Local BGE
        │
        ▼
Vector Database
  PostgreSQL + pgvector (document_chunks) or Qdrant + BM25 Hybrid Index
        │
        ▼
RAG Retrieval & Generation -> Grounded AI Response
  Semantic search · RRF fusion · Cross-encoder reranking · Citations (Document name, page, section)
```

## 1. Provision Private GCS Bucket & Pub/Sub Notification

The Terraform storage module (`terraform/modules/storage/main.tf`) provisions:
- `google_storage_bucket.uploads` with uniform bucket-level access, enforced public access prevention, soft delete, and lifecycle rules.
- `google_pubsub_topic.gcs_events` and `google_pubsub_topic.gcs_events_dlq` (dead-letter topic).
- `google_storage_notification.uploads_finalize` watching `OBJECT_FINALIZE` events under the `raw/` prefix.
- `google_pubsub_subscription.gcs_events_sub` with exponential backoff retry and dead-letter policy (`max_delivery_attempts = 5`).

To enable the required APIs manually when setting up Google Cloud:

```bash
gcloud services enable \
  storage.googleapis.com \
  pubsub.googleapis.com \
  aiplatform.googleapis.com \
  documentai.googleapis.com \
  --project YOUR_PROJECT_ID
```

## 2. Runtime Identity & Least-Privilege IAM

Grant the runtime service account (or local ADC identity):
- `roles/storage.objectUser` on the bucket (create, read, update, delete objects, and sign V4 URLs when using a service account).
- `roles/aiplatform.user` on the project when `EMBEDDING_PROVIDER=vertex_ai`.
- `roles/documentai.apiUser` on the project when `IMAGE_VISION_PROVIDER=document_ai`.

For local development with Docker Compose:

```bash
gcloud auth application-default login
export GOOGLE_APPLICATION_CREDENTIALS_HOST="$HOME/.config/gcloud/application_default_credentials.json"

docker compose -f docker-compose.yml -f docker-compose.gcs.yml up -d --build
```

## 3. Environment Configuration

```dotenv
# Object Storage & Pub/Sub
STORAGE_PROVIDER=gcs
GCS_BUCKET=your-private-bucket-name
GCS_PROJECT_ID=your-google-cloud-project-id
GCS_TIMEOUT_SECONDS=60
GCS_SIGNED_URL_EXPIRATION_SECONDS=900
PUBSUB_TOPIC_NAME=opennotebook-gcs-events
PUBSUB_VERIFICATION_TOKEN=your-shared-push-secret

# Vector Database (pgvector or qdrant)
VECTOR_STORE_PROVIDER=pgvector

# Embeddings (vertex_ai or local)
EMBEDDING_PROVIDER=vertex_ai
VERTEX_AI_LOCATION=us-central1
VERTEX_AI_EMBEDDING_MODEL=text-embedding-004
EMBEDDING_DIMENSION=384

# Image OCR / Vision (tesseract, gemini, or document_ai)
IMAGE_VISION_PROVIDER=tesseract
DOCUMENT_AI_PROCESSOR_NAME=

# LLM Provider (gemini, ollama, openai, anthropic)
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-1.5-flash
```

## 4. Upload, Signed URLs & Event-Driven Ingestion Flow

### Option A: Signed Upload URLs + Pub/Sub `OBJECT_FINALIZE`
1. Client calls `POST /api/v1/notebooks/{notebook_id}/sources/upload-url` with `{ "filename": "architecture.pdf", "content_type": "application/pdf", "size_bytes": 1048576 }`.
2. Backend creates a `Source` record in `UPLOADED` state (`storage_path = raw/{notebook_id}/{source_id}/architecture.pdf`) and returns a V4-signed `PUT` URL.
3. Client uploads the file bytes directly to Google Cloud Storage using the signed URL.
4. GCS emits an `OBJECT_FINALIZE` notification to Google Pub/Sub (`opennotebook-gcs-events`), which pushes to `POST /api/v1/events/gcs-finalize` (or the client calls `POST /api/v1/notebooks/{notebook_id}/sources/{source_id}/confirm-upload`).
5. The Pub/Sub handler verifies the object key and checks `generation` against `source.metadata_["processed_generations"]` for idempotency. Duplicate deliveries of the same GCS object generation are acknowledged without re-indexing.
6. The source transitions `UPLOADED -> QUEUED -> EXTRACTING -> CHUNKING -> EMBEDDING -> READY`.

### Option B: Direct Multipart Upload
1. Client calls `POST /api/v1/notebooks/{notebook_id}/sources/upload` with multipart form data.
2. Backend computes SHA-256, uploads the object to `gs://{GCS_BUCKET}/raw/{notebook_id}/{source_id}/{filename}`, records `storage_type=gcs`, and dispatches the background processing worker.

## 5. Verification

Run the unit test suite offline (no live GCP access required):

```bash
pytest backend/tests/unit/ -q --no-cov
```
