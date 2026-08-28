# Evaluation Service Dockerfile
#
# Build context MUST be the repository root, e.g.:
#   docker build -f apps/services/evaluation-service/Dockerfile -t evaluation-service .
# so that the shared `libs/` package is available alongside `src/`.
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install the service's dependencies (includes the runtime deps shared with libs).
COPY apps/services/evaluation-service/pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Shared cognitive libraries (Perception/Reasoning/Learning/...). The service
# imports `from libs...`; these must be present on the image.
COPY libs/ ./libs/

# Service source.
COPY apps/services/evaluation-service/src/ ./src/

EXPOSE 8102

ENV EVALUATION_HEALTH_PORT=8102 \
    EVALUATION_BATCH_SIZE=500 \
    EVALUATION_MAX_TENANTS=8

CMD ["python", "-m", "src.main"]
