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

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src/ ./src/

USER 1000:1000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OBSERVATION_BUS_URL=redis://redis:6379 \
    DATABASE_URL=postgresql+asyncpg://cosmonitor:cosmonitor@postgres:5432/cosmonitor \
    CONSUMER_GROUP=evidence_organizers \
    CONSUMER_NAME=collector-1

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import sqlalchemy, redis; print('OK')" || exit 1

ENTRYPOINT ["python", "-m", "src.main"]