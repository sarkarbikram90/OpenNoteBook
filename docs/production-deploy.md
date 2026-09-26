# Production Deployment Guide — Google Cloud Run

This guide documents the production deployment of **OpenNotebook** to **Google Cloud Platform (GCP)** using **Cloud Run**, **Artifact Registry**, and keyless **Workload Identity Federation (WIF)**.

---

## 1. Architecture Overview

OpenNotebook is deployed to GCP Cloud Run as serverless container microservices:

```
[User Browser]
       │
       ▼ (HTTPS)
┌──────────────────────────────────────────────┐
│  opennotebook-frontend (Cloud Run)           │
│  - React 19 SPA served via Nginx:alpine      │
│  - Listens on dynamic $PORT (default 8080)   │
│  - Rewrites /api/* to Cloud Run API backend  │
│  - Uses proxy_ssl_server_name on;            │
└──────────────────────┬───────────────────────┘
                       │
                       ▼ (HTTPS / Cloud Run URL)
┌──────────────────────────────────────────────┐
│  opennotebook-api (Cloud Run)                │
│  - FastAPI + Python 3.12 (Uvicorn)           │
│  - SSE streaming chat with citations         │
│  - Pluggable LLM & Vector Store connectors   │
└──────────────────────┬───────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Cloud SQL / │ │ Qdrant      │ │ Cloud       │
│ PostgreSQL  │ │ Vector DB   │ │ Storage     │
└─────────────┘ └─────────────┘ └─────────────┘
```

Container images are built and pushed to **Google Artifact Registry** in `us-central1` and deployed continuously via GitHub Actions.

---

## 2. Prerequisites & GCP Resources

* **GCP Project:** e.g., `founders-club-507318`
* **Region:** `us-central1`
* **Artifact Registry Repository:** `opennotebook` (`us-central1-docker.pkg.dev`)
* **Deployer Service Account:** `opennotebook-deployer@<PROJECT_ID>.iam.gserviceaccount.com`

---

## 3. Initial GCP Setup

Run these commands in **Google Cloud Shell** or your local terminal authenticated with `gcloud`:

### 3.1 Enable Required APIs
```bash
export PROJECT_ID="founders-club-507318"
export REGION="us-central1"

gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    iamcredentials.googleapis.com \
    cloudbuild.googleapis.com \
    --project=$PROJECT_ID
```

### 3.2 Create Artifact Registry Repository
```bash
gcloud artifacts repositories create opennotebook \
    --project=$PROJECT_ID \
    --location=$REGION \
    --repository-format=docker \
    --description="OpenNotebook Docker container images"
```

### 3.3 Create the Deployment Service Account & Assign Roles
```bash
# 1. Create service account
gcloud iam service-accounts create opennotebook-deployer \
    --project=$PROJECT_ID \
    --display-name="OpenNotebook Deployer"

# 2. Grant Cloud Run Admin (required to inspect, create, and update Cloud Run services)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:opennotebook-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/run.admin"

# 3. Grant Service Account User (required to assign runtime service identity)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:opennotebook-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"

# 4. Grant Artifact Registry Writer and Admin permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:opennotebook-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/artifactregistry.writer"

gcloud artifacts repositories add-iam-policy-binding opennotebook \
    --project=$PROJECT_ID \
    --location=$REGION \
    --member="serviceAccount:opennotebook-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/artifactregistry.writer"
```

---

## 4. Keyless Authentication via Workload Identity Federation (WIF)

Workload Identity Federation allows GitHub Actions to securely authenticate with GCP without storing long-lived private JSON keys.

### 4.1 Configure WIF in Google Cloud
```bash
export REPO="sarkarbikram90/OpenNoteBook"

# 1. Create Workload Identity Pool
gcloud iam workload-identity-pools create "github-pool" \
    --project=$PROJECT_ID \
    --location="global" \
    --display-name="GitHub Pool"

# 2. Create OIDC Provider
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
    --project=$PROJECT_ID \
    --location="global" \
    --workload-identity-pool="github-pool" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository == '${REPO}'"

# 3. Authorize GitHub repository to impersonate opennotebook-deployer
export WORKLOAD_IDENTITY_POOL_ID=$(gcloud iam workload-identity-pools describe "github-pool" \
    --project=$PROJECT_ID \
    --location="global" \
    --format="value(name)")

gcloud iam service-accounts add-iam-policy-binding \
    "opennotebook-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --project=$PROJECT_ID \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${WORKLOAD_IDENTITY_POOL_ID}/attribute.repository/${REPO}"

# 4. Get the Provider Resource Name
gcloud iam workload-identity-pools providers describe "github-provider" \
    --project=$PROJECT_ID \
    --location="global" \
    --workload-identity-pool="github-pool" \
    --format="value(name)"
```

### 4.2 Configure GitHub Repository Secrets
Navigate to **GitHub Repository → Settings → Secrets and variables → Actions** and add:

| Secret Name | Value Description |
|---|---|
| `WIF_PROVIDER` | Full resource name output from step 4.1 (e.g. `projects/123.../locations/global/workloadIdentityPools/github-pool/providers/github-provider`) |
| `WIF_SERVICE_ACCOUNT` | `opennotebook-deployer@founders-club-507318.iam.gserviceaccount.com` |
| `GCP_PROJECT_ID` | (Optional, defaults to `founders-club-507318`) |
| `GCP_REGION` | (Optional, defaults to `us-central1`) |
| `JWT_SECRET_KEY` | 64-character secret key for signing auth tokens |
| `DATABASE_URL` | PostgreSQL connection string |

---

## 5. CI/CD Deployment Pipeline (`.github/workflows/deploy.yml`)

The pipeline runs on every push to `main` or manual trigger via `workflow_dispatch`:

1. **Verify Job:** Runs full unit and evaluation regression test suites with pytest.
2. **Auth Step:** Exchanging GitHub OIDC token for a Google OAuth2 access token (`token_format: 'access_token'`).
3. **Registry Login:** Docker logs into Artifact Registry using `docker/login-action@v3` with `oauth2accesstoken`.
4. **Build & Push:** Builds images for `api`, `worker`, and `frontend`, tagging with commit SHA and `latest`.
5. **Deploy API:** Deploys `opennotebook-api` to Cloud Run with `--allow-unauthenticated`.
6. **Deploy Frontend:** Deploys `opennotebook-frontend` to Cloud Run, automatically injecting `BACKEND_URL` from the API deployment output.

---

## 6. Troubleshooting Common Issues

### 6.1 `PERMISSION_DENIED: Permission 'run.services.get' denied on resource 'namespaces/.../services/opennotebook-api'`
- **Cause:** The service account lacks permissions to manage Cloud Run services.
- **Fix:** Grant `roles/run.admin` and `roles/iam.serviceAccountUser` to `opennotebook-deployer@<PROJECT_ID>.iam.gserviceaccount.com`:
  ```bash
  gcloud projects add-iam-policy-binding $PROJECT_ID \
      --member="serviceAccount:opennotebook-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
      --role="roles/run.admin"
  gcloud projects add-iam-policy-binding $PROJECT_ID \
      --member="serviceAccount:opennotebook-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
      --role="roles/iam.serviceAccountUser"
  ```

### 6.2 `denied: Permission 'artifactregistry.repositories.uploadArtifacts' denied (or it may not exist)`
- **Cause:** Either the Docker repository `opennotebook` does not exist in the specified region, or the service account lacks upload permissions.
- **Fix:** Create the repository and assign `roles/artifactregistry.writer`:
  ```bash
  gcloud artifacts repositories create opennotebook --location=us-central1 --repository-format=docker
  gcloud artifacts repositories add-iam-policy-binding opennotebook \
      --location=us-central1 \
      --member="serviceAccount:opennotebook-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
      --role="roles/artifactregistry.writer"
  ```

### 6.3 `Key creation is not allowed on this service account (constraints/iam.disableServiceAccountKeyCreation)`
- **Cause:** The GCP organization policy blocks creating and downloading exportable private JSON service account keys.
- **Fix:** Use Workload Identity Federation (WIF) as documented in Section 4. WIF is completely keyless and satisfies this security constraint.

### 6.4 Supabase Database Connectivity on Cloud Run (IPv4 Pooler vs. Direct IPv6)
- **Cause:** Supabase direct database hostnames (`db.<project_ref>.supabase.co:5432`) only publish IPv6 `AAAA` DNS records. Google Cloud Run serverless container egress defaults to IPv4-only, causing direct connections from Cloud Run to fail with `Network unreachable` or unhandled connection errors (`500 Internal Server Error`).
- **Fix:** Connect via Supabase's **Transaction Pooler (Supavisor)** on port 6543 which provides public IPv4 routing and serverless connection pooling:
  - **Host:** `aws-1-ap-southeast-1.pooler.supabase.com` (or your project's assigned AWS region pooler)
  - **Port:** `6543` (Transaction pooler mode with `postgres.<project_ref>`)
  - **User:** `postgres.<project_ref>` (e.g. `postgres.ixjaquviwwtfrdenybxc`)
  - **Connection URI Format:**
    `postgresql://postgres.<project_ref>:<password>@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres`
  - *Note:* If your password contains `@` or special characters, URL-encode them (e.g., `getcracked@1990` becomes `getcracked%401990`). OpenNotebook automatically handles normalization, URL encoding, statement cache disablement, and maps direct Supabase hosts to IPv4 transaction poolers.

### 6.5 Default Demo Credentials & Account Creation
- **Default Pre-seeded Demo Account:**
  - **Email:** `demo@example.com`
  - **Password:** `password123`
- **Account Registration:**
  - Users can create new accounts directly via the frontend Sign Up tab (`/auth` -> Register).
  - Passwords are securely hashed with bcrypt (cost factor 12) and JWT access/refresh tokens are returned immediately upon login or registration.
