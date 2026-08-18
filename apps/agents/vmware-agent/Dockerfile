# Multi-stage: builder -> runtime
FROM python:3.11-slim AS builder

WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml .
RUN uv pip install --system --no-cache .

FROM python:3.11-slim AS runtime

# Non-root user (CIS hardening)
RUN groupadd -r cosmonitor && useradd -r -g cosmonitor -u 1000 -m cosmonitor

WORKDIR /app

# Copy only installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# App code
COPY src/ ./src/

# Security: read-only rootfs
USER 1000:1000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OBSERVATION_BUS_URL=redis://redis:6379 \
    TENANT_ID=00000000-0000-0000-0000-000000000001 \
    SOURCE_ID=00000000-0000-0000-0000-000000000001 \
    COLLECTION_INTERVAL_SECONDS=60

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import pyVmomi; print('OK')" || exit 1

ENTRYPOINT ["python", "-m", "src.main"]