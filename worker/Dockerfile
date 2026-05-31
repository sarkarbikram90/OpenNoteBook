# ─────────────────────────────────────────────
# OpenNotebook — Worker Dockerfile
# ─────────────────────────────────────────────
FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# Copy dependency manifest from backend (shared codebase)
COPY backend/pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy backend application source (worker uses the same code)
COPY backend/ .

# Switch to non-root user
USER appuser

# Health check via Celery inspect ping
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD celery -A app.worker.celery_app inspect ping --timeout 5 || exit 1

# Start Celery worker
CMD ["celery", "-A", "app.worker.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
