# ─────────────────────────────────────────────
# OpenNotebook — Backend Dockerfile
# ─────────────────────────────────────────────
FROM rust:1.83-slim AS rust-builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip && \
    pip install --no-cache-dir --break-system-packages maturin && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /rust
COPY rust/ ./
RUN maturin build --release --interpreter python3 --out /wheels

FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    HOME=/home/appuser

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        tesseract-ocr \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# Copy dependency manifest first (layer caching)
COPY pyproject.toml ./
COPY --from=rust-builder /wheels/*.whl /tmp/wheels/

# Install Python dependencies + compiled Rust opennotebook_core extension
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir /tmp/wheels/*.whl . && \
    rm -rf /tmp/wheels

# Copy application source
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 8080

# Health check (honors $PORT for Cloud Run; defaults to 8080 elsewhere)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/api/v1/health || exit 1

# Start the application (honors $PORT for Cloud Run; defaults to 8080 elsewhere)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
