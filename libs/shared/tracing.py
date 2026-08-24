"""Distributed tracing setup using OpenTelemetry (external, ADR-0002).

Provides a shared tracing configuration for all services. OpenTelemetry is the
industry standard for distributed tracing and exports spans to Jaeger/Tempo/
Datadog via OTLP.

Usage::

    from libs.shared.tracing import setup_tracing

    setup_tracing("context-service")  # Call once at service startup
"""
import logging
import os

logger = logging.getLogger(__name__)


def setup_tracing(service_name: str) -> None:
    """Initialize OpenTelemetry tracing for a service.

    Args:
        service_name: The name of the service (e.g., "context-service").

    Configuration via env vars:
        - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint (e.g., "http://jaeger:4317")
        - OTEL_SERVICE_NAME: Service name (overrides service_name param)
        - OTEL_TRACES_SAMPLER: Sampler type (e.g., "traceidratio")
        - OTEL_TRACES_SAMPLER_ARG: Sampler argument (e.g., "0.1" for 10%)
    """
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.debug("OTEL_EXPORTER_OTLP_ENDPOINT not set; tracing disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.sampling import (
            ALWAYS_ON,
            TraceIdRatioBased,
        )

        # Service resource.
        resource = Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", service_name),
                "service.version": os.getenv("APP_VERSION", "0.1.0"),
            }
        )

        # Sampler configuration.
        sampler_arg = float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "1.0"))
        if sampler_arg >= 1.0:
            sampler = ALWAYS_ON
        else:
            sampler = TraceIdRatioBased(sampler_arg)

        # Create provider with OTLP exporter.
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider = TracerProvider(
            resource=resource,
            sampler=sampler,
        )
        provider.add_span_processor(
            _BatchSpanProcessor(exporter)
        )

        trace.set_tracer_provider(provider)
        logger.info("OpenTelemetry tracing enabled: endpoint=%s service=%s", endpoint, service_name)

    except ImportError:
        logger.warning(
            "opentelemetry packages not installed; tracing disabled. "
            "Install with: pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-exporter-otlp"
        )
    except Exception:
        logger.exception("Failed to initialize OpenTelemetry tracing")


def _BatchSpanProcessor(exporter):
    """Lazy import of BatchSpanProcessor."""
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    return BatchSpanProcessor(exporter)
