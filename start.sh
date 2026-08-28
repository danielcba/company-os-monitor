#!/usr/bin/env bash
#
# start.sh - COS-Monitor platform boot.
#
# Boots the full cognitive pipeline in dependency order:
#   1. Environment (.env from .env.example if missing)
#   2. Python interpreter with the required dependencies
#   3. Infrastructure containers (postgres :5433, redis :6379)
#   4. Idempotent DB migrations (infrastructure/db-migrations)
#   5. Pipeline services (collector -> context -> pattern -> anomaly ->
#      hypothesis -> confidence -> recommendation -> decision -> report)
#      plus the external user-service (:8099) and api-gateway (:8100)
#   6. linux-agent observation capturer (:8080)
#
# Usage:
#   ./start.sh            boot the platform
#   ./start.sh --force    stop anything running first, then boot clean
#   ./start.sh --no-agent skip the observation agent
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

RUNTIME_DIR="$ROOT/.runtime"
LOG_DIR="$ROOT/logs"
COMPOSE_FILE="$ROOT/infrastructure/docker/docker-compose.yml"
MIGRATIONS_DIR="$ROOT/infrastructure/db-migrations"

HEALTH_WAIT_SECONDS="${HEALTH_WAIT_SECONDS:-40}"

# Service spec: name|app_dir|port_env|default_port
# IMPORTANT: keep in sync with stop.sh (stop.sh iterates this in reverse).
SERVICE_SPECS=(
  "collector|apps/services/collector-service|HEALTH_PORT|8090"
  "context|apps/services/context-service|ACTIVATOR_HEALTH_PORT|8091"
  "pattern|apps/services/pattern-service|PATTERN_HEALTH_PORT|8092"
  "anomaly|apps/services/anomaly-service|ANOMALY_HEALTH_PORT|8093"
  "hypothesis|apps/services/hypothesis-service|HYPOTHESIS_HEALTH_PORT|8094"
  "insight|apps/services/insight-service|INSIGHT_HEALTH_PORT|8101"
  "confidence|apps/services/confidence-service|CONFIDENCE_HEALTH_PORT|8095"
  "recommendation|apps/services/recommendation-service|RECOMMENDATION_HEALTH_PORT|8096"
  "decision|apps/services/decision-service|DECISION_HEALTH_PORT|8097"
  "evaluation|apps/services/evaluation-service|EVALUATION_HEALTH_PORT|8102"
  "report|apps/services/report-service|REPORT_HEALTH_PORT|8098"
  "user|apps/services/user-service|USER_HEALTH_PORT|8099"
  "gateway|apps/gateway/api-gateway|GATEWAY_HEALTH_PORT|8100"
)
AGENT_SPECS=(
  "linux-agent|apps/agents/linux-agent|AGENT_HEALTH_PORT|8080"
)

log() { printf '\033[1;34m[cos-monitor]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[cos-monitor]\033[0m ERROR: %s\n' "$*" >&2; exit 1; }

FORCE=0
START_AGENT=1
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --no-agent) START_AGENT=0 ;;
    -h|--help)
      sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) die "unknown argument: $arg" ;;
  esac
done

for tool in docker curl python3; do
  command -v "$tool" >/dev/null 2>&1 || die "required tool not found: $tool"
done
docker info >/dev/null 2>&1 || die "docker daemon not available (is it running?)"

resolve_python() {
  local candidate
  for candidate in "$ROOT/.venv/bin/python" python3; do
    if "$candidate" -c "import fastapi, aiohttp, asyncpg, redis, pydantic, sqlalchemy" >/dev/null 2>&1; then
      PYTHON="$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON=""
if ! resolve_python; then
  log "python dependencies missing - provisioning .venv (this can take a while)"
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/python" -m pip install --upgrade pip
  "$ROOT/.venv/bin/python" -m pip install -e ".[dev]"
  PYTHON="$ROOT/.venv/bin/python"
fi
log "python: $PYTHON"

if [ ! -f "$ROOT/.env" ]; then
  log "no .env found - copying .env.example (development defaults)"
  cp "$ROOT/.env.example" "$ROOT/.env"
fi
set -a
# shellcheck disable=SC1091
source "$ROOT/.env" || die "failed to parse $ROOT/.env (check for invalid syntax)"
set +a

# Host-side processes reach the containers through the published ports. If the
# env points at container-internal hostnames (redis://redis:6379 or
# ...@postgres:5432), normalize them to the host view (localhost:6379/5433).
case "$OBSERVATION_BUS_URL" in
  redis://redis:*) export OBSERVATION_BUS_URL="redis://localhost:6379" ;;
esac
case "$REDIS_URL" in
  redis://redis:*) export REDIS_URL="redis://localhost:6379" ;;
esac
case "$DATABASE_URL" in
  *@postgres:*)
    export DATABASE_URL="$(printf '%s' "$DATABASE_URL" |
      sed -E 's/@postgres:/@localhost:/; s|:5432/|:5433/|')"
    ;;
esac

mkdir -p "$RUNTIME_DIR" "$LOG_DIR"

check_running() {
  local f pid
  for f in "$RUNTIME_DIR"/*.pid; do
    [ -f "$f" ] || continue
    pid="$(cat "$f" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  done
  return 1
}

if check_running; then
  if [ "$FORCE" = "1" ]; then
    log "force: stopping running processes first"
    "$ROOT/stop.sh" >/dev/null 2>&1 || true
  else
    die "platform appears to be running (see .runtime/). Run ./stop.sh first, or ./start.sh --force"
  fi
fi

infra_up() {
  log "starting infrastructure (postgres :5433, redis :6379)"
  docker compose -f "$COMPOSE_FILE" up -d

  local i
  log "waiting for postgres"
  for i in $(seq 1 60); do
    if docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U cosmonitor >/dev/null 2>&1; then
      echo "  [ok] postgres ready"
      break
    fi
    [ "$i" = "60" ] && die "postgres did not become ready (docker compose logs postgres)"
    sleep 2
  done

  log "waiting for redis"
  for i in $(seq 1 30); do
    if docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
      echo "  [ok] redis ready"
      break
    fi
    [ "$i" = "30" ] && die "redis did not become ready (docker compose logs redis)"
    sleep 2
  done
}

apply_migrations() {
  log "applying DB migrations (idempotent)"
  local f
  for f in "$MIGRATIONS_DIR"/*.sql; do
    [ -f "$f" ] || continue
    if docker compose -f "$COMPOSE_FILE" exec -T postgres \
        psql -U cosmonitor -d cosmonitor -v ON_ERROR_STOP=1 -q -f - \
        < "$f" >>"$LOG_DIR/migrations.log" 2>&1; then
      echo "  [ok] $(basename "$f")"
    else
      echo "  [!!] $(basename "$f") failed (see logs/migrations.log)" >&2
      return 1
    fi
  done
}

wait_health() {
  local name="$1" port="$2" i
  for i in $(seq 1 "$HEALTH_WAIT_SECONDS"); do
    if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

start_one() {
  local spec="$1" name dir port_var default_port port rest pidfile pid
  name="${spec%%|*}"; rest="${spec#*|}"
  dir="${rest%%|*}"; rest="${rest#*|}"
  port_var="${rest%%|*}"; default_port="${rest#*|}"
  port="${!port_var:-$default_port}"

  pidfile="$RUNTIME_DIR/$name.pid"
  if [ -f "$pidfile" ]; then
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo "  [skip] $name already running (pid $pid)"
      return 0
    fi
    rm -f "$pidfile"
  fi

  echo "  [start] $name -> http://127.0.0.1:$port/health (logs/$name.log)"
  PYTHONPATH="$ROOT/$dir:$ROOT" "$PYTHON" -m src.main >>"$LOG_DIR/$name.log" 2>&1 &
  echo $! > "$pidfile"

  if ! wait_health "$name" "$port"; then
    echo "  [!!] $name did not become healthy within ${HEALTH_WAIT_SECONDS}s (see logs/$name.log)" >&2
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
    rm -f "$pidfile"
    return 1
  fi
  echo "  [ok] $name healthy"
}

infra_up
apply_migrations || die "DB migrations failed (see logs/migrations.log)"

log "starting pipeline services + auth + gateway"
for spec in "${SERVICE_SPECS[@]}"; do
  start_one "$spec" || die "failed to start ${spec%%|*}"
done

if [ "$START_AGENT" = "1" ]; then
  log "starting observation agents"
  for spec in "${AGENT_SPECS[@]}"; do
    start_one "$spec" || die "failed to start ${spec%%|*}"
  done
fi

log "COS-Monitor is up"
log "endpoints"
for spec in "${SERVICE_SPECS[@]}" "${AGENT_SPECS[@]}"; do
  name="${spec%%|*}"; rest="${spec#*|}"
  rest="${rest#*|}"
  port_var="${rest%%|*}"; default_port="${rest#*|}"
  printf '  %-15s http://127.0.0.1:%s/health\n' "$name" "${!port_var:-$default_port}"
done
log "infrastructure: postgres :5433, redis :6379 (docker compose)"
log "logs: logs/*.log  -  stop: ./stop.sh"