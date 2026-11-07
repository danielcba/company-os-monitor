# 2026-09-28 — Production readiness & governance audit (prompt `correccion_37.md`)

## Propósito

Auditoría read-only de Production Readiness + GitHub Governance sobre el
release actual, con clasificación de cada hallazgo
(RESOLVED / EXTERNAL / ARCHITECTURAL DECISION / CODE CHANGE / BLOCKER) y
cambios locales mínimos **solo** para hallazgos categoría-4 inequívocos.
**Sin Sprint 13, sin commit (`AUTHORIZE_COMMIT` no aparece YES), sin push.**
Framework = solo lectura (0 escrituras).

## Baseline (FASE 0/1 — verificado)

- **Monitor**: `HEAD = origin/main = ls-remote =
  e32fb883dc6c415d2baeb646d7a99ed24e04b898` (parent
  `3d1809047ef7f640140ac1ee30a439fc97249f2f`, msg
  `security: restrict compose published ports to loopback`); ahead/behind
  0/0; worktree limpio al inicio (0 M, 0 staged, 0 ??).
- **CI baseline**: run `36463979777` sobre `e32fb883` =
  completed/**success** (2/2: `lint-and-test (3.12, 24)`, `docker-build`).
  Últimos 3 runs: todos success (`e32fb883`, `fbf760d2`, `84d73a01`).
- **Ancestros**: U6a `7ca822d…`, U6b `079024e…`, U7 `65f528f…` ✓.
- **Framework**: `381f56cfa48d092f85846e160d2e1fe6878f9f6f` (el SHA literal
  `…f9f6f9f` del prompt es errata; verificado con ls-remote). Worktree con
  9 entradas **preexistentes** (4 M + 5 ??) preservadas intactas;
  `git status journal/` Framework = 0 escrituras ✓. Framework escrito: NO.
- Runtime preexistente: solo `docker-postgres-1` (bind `127.0.0.1:5433`);
  procesos de servicio: 0.

## Hallazgos y clasificación

| # | Hallazgo | Evidencia (verificada en vivo) | Clase |
|---|---|---|---|
| F1 | `start.sh` gate de readiness de Redis sin autenticar contra `--requirepass` | `start.sh:214` ejecutaba `redis-cli ping` → `NOAUTH Authentication required.` → `die "redis did not become ready"` tras 60s. Probe escrito en `0be8241`; `requirepass` añadido en `e3d5a5c`/`d98133f` sin actualizarlo | **RESOLVED** — CODE CHANGE aplicado (mínimo) |
| F2 | `stop.sh` no carga `.env` → `docker compose down` falla con interpolación fail-closed | `stop.sh:79` sin env → `error while interpolating … POSTGRES_PASSWORD is required` → contenedores NO se bajaban (rc=0 igual, solo warn). `:?` entró en `d98133f` después de crear `stop.sh` (`0be8241`) | **RESOLVED** — CODE CHANGE aplicado (mínimo) |
| F3 | Conflicto de puerto 8080: frontend container (`127.0.0.1:8080`) vs `linux-agent` health server (`0.0.0.0:8080`) | Arranque real del agente → `OSError: [Errno 98] … bind on address ('0.0.0.0', 8080): address already in use`, rc=1. Frontend añadido en `249f475` (después de `9635775`). `AGENT_HEALTH_PORT` declarado en `start.sh:50` pero **ignorado** por `apps/agents/linux-agent/src/health.py:21-24` (`port=8080` hardcodeado) | **OPEN — CODE CHANGE requiere decisión de dueño** (no aplicado: dos correcciones mínimas compiten; decisión de asignación de puerto, fuera de mi autoría). Workaround documentado: `./start.sh --no-agent` (boot completo verificado) |
| F4 | Code scanning no configurado | `code-scanning/alerts` = 404 "no analysis found"; sin workflow CodeQL; SAST local = bandit/ruff en CI | **OPEN — EXTERNAL** (habilitación = settings/decisión explícita) |
| F5 | `secret_scanning_validity_checks=disabled`, `non_provider_patterns=disabled` | `security_and_analysis`: scanning=enabled, push_protection=enabled, validity=disabled | **OPEN — EXTERNAL** |
| F6 | Branch protection: `enforce_admins=false`, `dismiss_stale=false`, `code_owner=false`, `last_push=false` | API: strict=true, checks `["lint-and-test (3.12, 24)","docker-build"]`, approvals=1, `required_signatures=true`, force-push/deletions=false, restrictions=null, rulesets=0 | **OPEN — EXTERNAL** (ya endurecido parcialmente en correccion_34) |
| F7 | Actions: `allowed_actions=all`, `sha_pinning_required=false` (ci.yml sí pina 4 uses por SHA + `persist-credentials:false`, `permissions: contents: read`) | API actions/permissions | **OPEN — EXTERNAL** (política) |
| F8 | 0 release tags (local y remoto) | `git tag` = 0, `ls-remote --tags` = 0 | **OPEN — ARCHITECTURAL DECISION** (policy de tagging de release; recomendación) |
| F9 | Servicios del host en `0.0.0.0` alcanzan la LAN | Live: `192.168.100.64:8100` CONNECTED; contenedores SÍ en loopback (`ss`: 5433/6379/8080 = `127.0.0.1`), frontend LAN rechazado | **OPEN — ARCHITECTURAL DECISION** (recomendación preexistente de hardening; no nuevo, no cambiado) |
| F10 | CODEOWNERS = único owner `@danielcba`; repo **public** | `.github/CODEOWNERS`; repo API `visibility: public` | **OBSERVATION — EXTERNAL** |

Resumen: 2 RESOLVED (cambios aplicados), 5 EXTERNAL, 2 ARCHITECTURAL
DECISION (recomendación), 1 CODE CHANGE pendiente de decisión (F3).
BLOCKER: ninguno para release (F3 tiene workaround `--no-agent`
verificado); F3 es el único defecto local abierto del boot por defecto.

## Cambios locales aplicados (mínimos, categoría-4)

1. **`start.sh:214`** — probe autenticado:
   `redis-cli -a "${REDIS_PASSWORD:?REDIS_PASSWORD is required}" --no-auth-warning ping`.
2. **`stop.sh`** — carga de `.env` (`set -a; source …; set +a`) con warn
   best-effort si falta, reflejando el patrón de `start.sh`; sin él el
   `:?` de compose impedía el `down`.

Diff final: **2 archivos, 2 líneas lógicas** (`start.sh` 1, `stop.sh` 9).
No se tocaron compose binds, `.env`, tests, ni ningún archivo Python.

## Validación

- `bash -n start.sh` y `bash -n stop.sh` ✓; `git diff --check` ✓; YAML (ci,
  dependabot, secret_scanning, compose) ✓.
- Tests afectados: `test_d01_failclosed.py` + `test_migrations_idempotency`
  = **26 passed**. Suite completa **`pytest tests/` = 766 passed** (rc=0).
- Gates: `ruff check .` ✓; mypy con los scopes exactos de CI (libs/,
  gateway, services) ✓; `compileall` ✓. Frontend **sin cambios** (`git status` solo
  shell) → npm lint/typecheck/test omitidos con justificación.
- **Boot empírico**: `./start.sh --no-agent` → rc=0, `COS-Monitor is up`,
  13 servicios healthy (collector…gateway); gateway
  `{"status":"healthy"}`; frontend HTTP 200 en loopback; LAN a :8080
  rechazado; `ss` confirma binds loopback de los 3 puertos publicados.
- **F3 empírico**: agente real → EADDRINUSE (rc=1) mientras frontend retiene
  8080.
- **Stop/cleanup**: `./stop.sh` ahora ejecuta `down` OK
  (contenedores removidos, red removida), volúmenes
  `docker_postgres_data`/`docker_redis_data` preservados (sin `-v`);
  runtime restaurado al estado preauditoría: solo `docker-postgres-1`
  corriendo; 0 procesos de servicio.

## Not hecho (explícito)

- Sin commit, sin push (defaults NO), CI no se dispara (N/A).
- Sin Sprint 13, sin features, sin contenido comercial.
- Framework intacto; journals del Framework: 0 escrituras.
- F3 no corregido (decisión de puerto requerida); F4–F9 no alterados
  (settings/decisiones externas).

## Estado final

`COMMIT CREATED: NO` · `PUSH PERFORMED: NO` · `CI: N/A`
