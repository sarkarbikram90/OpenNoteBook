"""OpenNotebook — Structured Logging and OpenTelemetry Tracing Configuration.

Sets up structured JSON logging using python-json-logger and configures the
OpenTelemetry SDK to export spans to Tempo/OTLP collector.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure structured JSON logging or standard console logging."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Base configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    if settings.log_format.lower() == "json":
        # Structured JSON Logging
        from pythonjsonlogger import jsonlogger

        handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(
            fmt="%(timestamp)s %(level)s %(name)s %(message)s %(trace_id)s %(span_id)s",
            rename_fields={"levelname": "level", "asctime": "timestamp"},
            json_ensure_ascii=False,
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    else:
        # standard colored log format for development
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # Silence noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("qdrant_client").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)


def init_tracing(service_name: str) -> None:
    """Initialize OpenTelemetry tracer provider and OTLP exporter.

    Args:
        service_name: Name of the microservice (e.g. 'api', 'worker')
    """
    settings = get_settings()

    # Create resource attributes
    resource = Resource.create(
        attributes={
            "service.name": f"{settings.app_name}-{service_name}",
            "service.namespace": settings.app_name,
            "deployment.environment": settings.app_env,
        }
    )

    provider = TracerProvider(resource=resource)

    # Endpoint is typically retrieved from environment (OTEL_EXPORTER_OTLP_ENDPOINT)
    # Defaulting to localhost/tempo grpc port if not defined
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317")

    try:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        logger.info("OpenTelemetry tracing initialized for service: %s", service_name)
    except Exception as e:
        logger.warning("Failed to initialize OpenTelemetry OTLP exporter: %s. Tracing disabled.", e)
        # Fallback to NoOp TracerProvider
        trace.set_tracer_provider(TracerProvider())


def get_tracer(name: str) -> Any:
    """Get an OpenTelemetry tracer instance."""
    return trace.get_tracer(name)
