#!/usr/bin/env bash
#
# stop.sh - COS-Monitor platform shutdown.
#
# Shuts the platform down as cleanly as possible, in reverse boot order:
#   1. Graceful SIGTERM to every service/agent process (20s grace, then SIGKILL)
#   2. Infrastructure containers (postgres, redis) via docker compose down
#   3. Runtime bookkeeping cleanup (.runtime pids)
#
# Data volumes (postgres_data, redis_data) are preserved: `down` without -v.
#
# Usage:
#   ./stop.sh            stop the platform
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

RUNTIME_DIR="$ROOT/.runtime"
LOG_DIR="$ROOT/logs"
COMPOSE_FILE="$ROOT/infrastructure/docker/docker-compose.yml"

GRACE_SECONDS="${GRACE_SECONDS:-20}"

# Service spec: name|app_dir|port_env|default_port
# IMPORTANT: keep in sync with start.sh (this list is the reverse boot order).
STOP_SPECS=(
  "linux-agent|apps/agents/linux-agent|AGENT_HEALTH_PORT|8080"
  "gateway|apps/gateway/api-gateway|GATEWAY_HEALTH_PORT|8100"
  "user|apps/services/user-service|USER_HEALTH_PORT|8099"
  "report|apps/services/report-service|REPORT_HEALTH_PORT|8098"
  "decision|apps/services/decision-service|DECISION_HEALTH_PORT|8097"
  "recommendation|apps/services/recommendation-service|RECOMMENDATION_HEALTH_PORT|8096"
  "confidence|apps/services/confidence-service|CONFIDENCE_HEALTH_PORT|8095"
  "hypothesis|apps/services/hypothesis-service|HYPOTHESIS_HEALTH_PORT|8094"
  "anomaly|apps/services/anomaly-service|ANOMALY_HEALTH_PORT|8093"
  "pattern|apps/services/pattern-service|PATTERN_HEALTH_PORT|8092"
  "context|apps/services/context-service|ACTIVATOR_HEALTH_PORT|8091"
  "collector|apps/services/collector-service|HEALTH_PORT|8090"
)

log() { printf '\033[1;34m[cos-monitor]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[cos-monitor]\033[0m %s\n' "$*" >&2; }

command -v docker >/dev/null 2>&1 || warn "docker not found - skipping container shutdown"

stopped=0
if [ -d "$RUNTIME_DIR" ]; then
  log "stopping platform processes (reverse boot order)"
  for spec in "${STOP_SPECS[@]}"; do
    name="${spec%%|*}"
    pidfile="$RUNTIME_DIR/$name.pid"
    [ -f "$pidfile" ] || continue
    pid="$(cat "$pidfile" 2>/dev/null || true)"

    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo "  [stop] $name (pid $pid)"
      kill "$pid" 2>/dev/null || true
      for _ in $(seq 1 "$GRACE_SECONDS"); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
      done
      if kill -0 "$pid" 2>/dev/null; then
        warn "  $name did not exit gracefully after ${GRACE_SECONDS}s - sending SIGKILL"
        kill -9 "$pid" 2>/dev/null || true
      fi
      stopped=1
    fi
    rm -f "$pidfile"
  done
  rm -rf "$RUNTIME_DIR"
fi

if command -v docker >/dev/null 2>&1; then
  log "stopping infrastructure containers (data volumes preserved)"
  if docker compose -f "$COMPOSE_FILE" down; then
    echo "  [ok] containers stopped"
  else
    warn "  docker compose down reported an error (is the daemon running?)"
  fi
fi

if [ "$stopped" = "1" ]; then
  log "done"
else
  log "nothing was running - platform already stopped"
fi