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

# The libs/ packages are expected on the image root as `libs/` (mounted or copied).
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src/ ./src/

USER 1000:1000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL=postgresql+asyncpg://cosmonitor:cosmonitor@postgres:5432/cosmonitor \
    HYPOTHESIS_HEALTH_PORT=8094 \
    HYPOTHESIS_CYCLE_SECONDS=60 \
    LM_STUDIO_URL=http://lm-studio:1234/v1

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import sqlalchemy, asyncpg; print('OK')" || exit 1

ENTRYPOINT ["python", "-m", "src.main"]
