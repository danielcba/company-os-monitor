# 2026-09-28 — Post-release hardening audit (prompt `correccion_34.md`)

## Propósito

Auditoría y hardening post-release sobre las limitaciones NO bloqueantes del
último RELEASE CLOSURE AUDIT (branch protection, code scanning, secret
scanning validity checks, compose binds). **Sin Sprint 13, sin features
nuevas, sin contenido comercial.** Framework = solo lectura.

## Baseline (verificado con `git fetch --prune` antes de analizar)

- **Monitor**: branch `main`; `HEAD = origin/main = ls-remote =
  3d1809047ef7f640140ac1ee30a439fc97249f2f`; parent
  `65f528f22959198eaf239b1251fde838c2cd5e73`; ahead 0 / behind 0; worktree
  **limpio** (0 M, 0 staged, 0 ??) al inicio.
- **U6a `7ca822d…`, U6b `079024e…`, U7 `65f528f…`** = ancestros verificados ✓.
- **CI del baseline**: run `36374505993` sobre `3d18090…` =
  completed/success; jobs `lint-and-test (3.12, 24)` = success,
  `docker-build` = success (evidencia actual, no histórica).
- **Framework** (`company-os`): `HEAD = origin/main = ls-remote =
  381f56cfa48d092f85846e160d2e1fe6878f9f6f` ✓. Worktree con 9 entradas
  **preexistentes** (4 M + 5 ??, mtime 2026-09-18) idénticas a las
  documentadas en la auditoría 2026-09-27 — clasificadas PRE-EXISTING,
  preservadas sin tocar. Journal del Framework: `git status journal/` = 0
  escrituras ✓. Framework escrito por esta tarea: NO.
- Estado runtime preexistente: `docker-postgres-1` corriendo (bind previo
  `0.0.0.0:5433`), sin redis ni frontend corriendo; sin procesos pytest /
  servicios activos.

## Limitaciones auditadas (estado ACTUAL verificado, no asumido)

| # | Limitación | Estado verificado (FACT) | Clase |
|---|---|---|---|
| 1 | Branch protection débil | API: `enforce_admins=false`, `dismiss_stale_reviews=false`, `require_code_owner_reviews=false`, `require_last_push_approval=false`, `required_approving_review_count=1`, `strict=true`, contexts `["lint-and-test (3.12, 24)","docker-build"]`, `required_signatures=true`, force-push/deletions = false | OPEN — EXTERNAL/HUMAN SETTINGS |
| 2 | Code scanning ausente | API code-scanning alerts = 404 "no analysis found"; SAST local = `bandit` gate en CI | OPEN — EXTERNAL (habilitación = settings/decisión explícita) |
| 3 | `secret_scanning_validity_checks=disabled` | API `security_and_analysis`: `secret_scanning=enabled`, `push_protection=enabled`, `validity_checks=disabled`; `gh secret list` vacío | OPEN — EXTERNAL/HUMAN SETTINGS |
| 4 | Compose binds `0.0.0.0` | `infrastructure/docker/docker-compose.yml` (único compose del repo): `5433:5432`, `6379:6379`, `8080:8080` → publicación en todas las interfaces | OPEN → corregido (ver Decisión) |

## Análisis de #4 (evidencia recogida en esta ejecución)

- **Único archivo compose** del repo (0 variantes/ignorados). `0.0.0.0`
  explícito también en los `TCPSite` de los servicios → son procesos en el
  host, no publicaciones compose; fuera del alcance de #4 (recomendación,
  sin cambio).
- **Consumidores de 5433/6379/8080**: todos host-locales —
  `start.sh` normaliza URLs a `localhost` (líneas 112-134) y arranca los 13
  servicios + agentes nativamente en el host; tests usan `127.0.0.1:5433`
  (`tests/architecture/test_insight_schema.py:32`); el navegador (host)
  consume el frontend y la API en localhost.
- **Container → host**: el nginx del frontend no tiene `proxy_pass`
  (SPA + `connect-src 'self' http://localhost:*`); ningún servicio compose
  contacta puertos publicados del host; el tráfico inter-contenedor usa
  `postgres:5432`/`redis:6379` dentro de la red compose (no depende del
  bind del host).
- **Agentes remotos**: el canal canónico es
  `POST /api/v1/telemetry/ingest` con machine JWT vía Gateway
  (ADR-0004 §2, ADR-0005; SECURITY.md "agent-to-gateway authentication");
  el Gateway corre en el host (`:8100`, no compose) y no se toca. Publicar
  Redis/Postgres a la LAN no es un canal documentado ni canónico.
- **CI**: el job `lint-and-test` usa *service containers* de GitHub Actions
  (mapeo del runner, independiente del compose); `docker-build` solo ejecuta
  `compose build` (sin publicación de puertos).
- **Decisión (regla Fase 6.B)**: corrección local segura, mínima y
  compatible con Framework (R1–R7 y `.github` del Framework no contienen
  política de binding; la separación Framework → Monitor no se altera).

## Cambios realizados

1. `infrastructure/docker/docker-compose.yml` — **3 líneas**, bind loopback:
   `127.0.0.1:5433:5432`, `127.0.0.1:6379:6379`, `127.0.0.1:8080:8080`.
   Nada más en el archivo (fail-closed `:?` intacto, healthchecks intactos).
2. Este journal (append-only, archivo nuevo).
3. Runtime: `docker-postgres-1` recreado con el nuevo bind
   (`docker compose … up -d postgres`); volumen y datos preservados;
   contenedor sigue corriendo (ahora `127.0.0.1:5433`). Smoke de
   redis/frontend hecho en proyecto temporal `cosbind-smoke`, **eliminado
   al terminar** (containers, volumen, red e imagen: 0 residuos).

## Validaciones (sobre el estado EXACTO final)

| Gate | Resultado |
|---|---|
| `git diff --check` | rc=0 |
| YAML (`docker-compose.yml`, `ci.yml`, `dependabot.yml`, `secret_scanning.yml`) | `yaml.safe_load` OK (4/4) |
| `docker compose config` sin credenciales | rc=1 (fail-closed preservado) |
| `docker compose config` con `.env` | rc=0; rendered = `host_ip: 127.0.0.1` en los 3 puertos |
| `ruff check .` | rc=0 |
| `mypy --config-file mypy.ini libs/` | Success, 70 files |
| `bandit -r apps/ libs/ -ll -c bandit.yaml` | rc=0 (0 issues ≥ medium) |
| `python3 -m compileall apps libs` | rc=0 |
| `pytest tests/` | **766 passed** |
| `pytest tests/security tests/architecture` | **321 passed** |
| Frontend lint / typecheck / test | 0 errores (4 warnings preexistentes) / OK / **182 passed** |
| Smoke postgres (bind nuevo) | `127.0.0.1:5433` CONNECTED; `192.168.100.64:5433` ConnectionRefused; datos preservados |
| Smoke redis (temp) | auth+ping `127.0.0.1:6379` OK; LAN ConnectionRefused |
| Smoke frontend (temp) | HTTP 200 `127.0.0.1:8080`; LAN curl rc=7 (no expuesto) |
| 0 secretos añadidos / 0 contenido comercial / 0 cambios Framework / U6a-U6b-U7 intactos | verificado por `git status` + `git diff` + API |

Sin skips/xfails nuevos; sin cambios de workflow; sin cambios de configuración
de tests.

## Limitaciones externas (sin modificar — EXTERNAL/HUMAN SETTINGS)

- #1 branch protection, #2 code scanning, #3 `validity_checks=disabled`:
  requieren GitHub settings / habilitación humana; API solo-lectura
  consultada, 0 writes.
- Exposición `0.0.0.0` de los `TCPSite` de gateway/servicios/agentes en el
  host: recomendación de hardening futuro (decisión de despliegue; el
  gateway debe seguir alcanzable para el canal canónico agent→gateway).

## Autorización

- `AUTHORIZE_COMMIT=NO`, `AUTHORIZE_PUSH=NO` (prompt 34) → **sin commit, sin
  push, sin staging**. Estado revisable: `1 M` (compose) + `1 ??` (este
  journal). Sin SHA futuros, sin credenciales registradas.
