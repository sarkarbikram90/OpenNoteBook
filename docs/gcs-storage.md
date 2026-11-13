# Google Cloud Storage for OpenNoteBook

OpenNotebook can use a private Google Cloud Storage bucket as its authoritative
object store for uploaded source files and derived processing artifacts. The
existing Celery ingestion pipeline, BGE embeddings, Qdrant vector index, BM25
hybrid retrieval, reranker and citation-aware LLM generation remain in place.

## 1. Provision a private bucket

The production Terraform storage module already defines a Cloud Storage bucket.
The bucket must have uniform bucket-level access and public access prevention
enabled. Enable the Storage API:

```bash
gcloud services enable storage.googleapis.com --project YOUR_PROJECT_ID
```

## 2. Grant runtime access

Grant the identity used by both the API and Celery worker bucket-level
`roles/storage.objectUser` on the bucket. This permits object creation,
reading, updating and deletion without granting bucket administration.

For local development:

```bash
gcloud auth application-default login
```

For Cloud Run, attach a dedicated runtime service account and grant the same
bucket-scoped role to that service account. Do not store service-account JSON
keys in the repository, container image or `.env` file.

## 3. Configure OpenNotebook

Set these variables in the backend environment:

```dotenv
STORAGE_PROVIDER=gcs
GCS_BUCKET=your-private-bucket-name
GCS_PROJECT_ID=your-google-cloud-project-id
GCS_TIMEOUT_SECONDS=60
```

The bucket must exist before the application starts. The application does not
create buckets automatically. API and worker processes must use the same GCS
configuration and Google identity.

## 4. Ingestion and retrieval flow

1. The authenticated API validates notebook ownership, file type and size.
2. It computes SHA-256 and stores the original object in GCS under
   `raw/{notebook_id}/{source_id}/{filename}`.
3. The database records `storage_type=gcs` and the object key.
4. The existing Celery task downloads the object from its recorded provider.
5. The existing extractor, PII redaction, chunker and BGE embedding pipeline
   process the document.
6. Qdrant stores vectors and ACL-aware chunk payloads; BM25 builds lexical
   indexes.
7. The RAG orchestrator retrieves authorized chunks and streams grounded LLM
   responses with citations.

Processed text and metadata artifacts are written to the same provider recorded
for the source. Re-indexing therefore does not require re-uploading.

## 5. Supported files and image limitation

The upload UI and API accept PDF, DOCX, TXT, Markdown, JPEG, PNG, WEBP and TIFF.
Raster image files are passed through Tesseract OCR and indexed as text.

Image ingestion currently extracts **text visible in the image**. It does not
generate visual embeddings, image captions or visual similarity search. A
future multimodal phase can add Gemini/Vertex AI vision descriptions and
multimodal retrieval.

## 6. Existing documents

Changing `STORAGE_PROVIDER` does not copy existing objects between providers.
Each source retains its recorded `storage_type`, so existing local or MinIO
sources continue to be read and deleted from their original provider. Newly
uploaded documents use GCS after the configuration change. To make the entire
historical corpus GCS-only, run a separately verified migration and checksum
validation before removing the old storage.

## 7. Verification

- Upload a PDF, text file and image through the UI.
- Confirm raw objects appear in the private GCS bucket.
- Confirm source rows have `storage_type=gcs`.
- Wait for Celery status to reach `READY`.
- Ask questions about the uploaded documents and verify citations.
- Re-index a source and verify its raw object is downloaded from GCS.
- Delete a source and verify its GCS object is removed.
