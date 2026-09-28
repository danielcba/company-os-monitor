# 2026-09-28 — F3 agent health port resolution (prompt `correccion_39.md`)

## Propósito

Cierre de F3 (colisión 8080 frontend vs linux-agent) con la decisión
arquitectónica **autorizada por esta tarea**: `AGENT_HEALTH_PORT=8103`.
Sin Sprint 13, sin features nuevas, sin Framework, sin settings remotos,
sin U6a/U6b/U7, sin contenido comercial.
`AUTHORIZE_COMMIT`/`AUTHORIZE_PUSH` ausentes → sin commit, sin push.

## Baseline (FASE 0 — verificado con `git fetch --prune`)

- **Monitor**: `HEAD = origin/main = ls-remote =
  e32fb883dc6c415d2baeb646d7a99ed24e04b898`; branch `main`; ahead/behind
  0/0; staged 0; U6a `7ca822d…`, U6b `079024e…`, U7 `65f528f…` ancestros ✓.
- **CI baseline**: run `36463979777` sobre `e32fb883` = success (2/2) ✓.
- **Estado preexistente registrado y preservado** (correccion_37, sin
  commit): ` M start.sh` (fix del probe Redis autenticado, línea 214),
  ` M stop.sh` (+11: carga de `.env`), `?? journal/…-production-readiness-governance-audit.md`,
  `?? journal/…-f3-agent-port-architectural-decision.md` (correccion_38).
- **Framework**: `381f56cfa48d092f85846e160d2e1fe6878f9f6f` =
  HEAD = origin = ls-remote; 9 entradas preexistentes intactas;
  journal Framework = 0 escrituras ✓.

## Problema F3 (evidencia)

`health.py:21` hardcodeaba `port: int = 8080` y `main.py` llamaba
`health.start()` sin argumento → el agente ignoraba `AGENT_HEALTH_PORT`
(definido en `start.sh:50`/`stop.sh:29` con default 8080) y colisionaba
con el frontend nginx publicado en `127.0.0.1:8080`
(`compose:39`, `nginx.conf:19`, `Dockerfile EXPOSE 8080`):
`OSError: [Errno 98] … ('0.0.0.0', 8080): address already in use`.
La tabla `cognitive_contract.md` §"Puertos del Sistema" asignaba
`8080: Linux Agent` (escrito en `02ed143`, 2026-08-30) mientras el
frontend tomó 8080 en `249f475` (2026-09-16) sin actualizarla.

## Verificación de 8103 antes de implementar (FASE 1)

- `git grep 8103` sobre archivos trackeados: **0 hits**; sin 8103 en
  código, compose, `.env(.example)`, tests, docs, historial
  (`git log -S`), ramas (`git grep` sobre todas) ni Framework.
- Único valor histórico de `AGENT_HEALTH_PORT` (todas las ramas):
  `8080`. Familia de agentes: windows=8081, vmware=8082 (código propio,
  no publicado aquí, fuera de la tabla del contrato).
- `ss -ltn`: 8103 **libre**; compose solo publica 5433/6379/8080.
- Conclusión: `8103` no ocupado ni contradicho → sin
  `ARCHITECTURAL DECISION CONFLICT`.

## Decisión arquitectónica (del Monitor, no del Framework)

`AGENT_HEALTH_PORT=8103` — efectivo y canónico en todas las expresiones
del contrato; `8080` queda **reservado al frontend** (`127.0.0.1:8080`);
alternativa "mover el frontend" descartada por la tarea.

## Archivos modificados (diff conceptual)

1. `apps/agents/linux-agent/src/health.py` — `start(port: int)` sin
   default (elimina el hardcode 8080).
2. `apps/agents/linux-agent/src/main.py` — único parseo
   `port = int(os.getenv("AGENT_HEALTH_PORT", "8103"))` (fail-closed:
   valor no numérico → `ValueError` antes de abrir puerto, convención
   idéntica a los servicios, p.ej. `collector main.py:27`) +
   `await health.start(port)` explícito.
3. `.env.example` — bloque `AGENT_HEALTH_PORT=8103` con racional
   (junto a la sección de agentes).
4. `.env` (local, **gitignored** — no se versiona) —
   `AGENT_HEALTH_PORT=8103`; el resto del archivo preservado.
5. `start.sh` — spec `…|AGENT_HEALTH_PORT|8103` (línea 50) y comentario
   `(:8103)` (línea 13). El cambio preexistente de correccion_37 (probe
   Redis autenticado) preservado byte por byte.
6. `cognitive_contract.md` — `8080: Frontend (nginx)` (reemplaza
   `8080: Linux Agent`) y `+8103: Linux Agent` (fin de la tabla,
   orden ascendente). Sin tabla paralela.
7. `docs/frontend/architecture.md:518` — rango `(8080–8100)` →
   `(8090–8100)` (8080 ya no es endpoint de servicios/agente).
8. **`stop.sh` NO modificado** (revisado): su campo `default_port` es
   datos muertos (solo parsea `name` para el pidfile) → sin necesidad
   técnica demostrable, según FASE 2.3; su diff preexistente queda intacto.

## Tests (nuevos — FASE 2.6)

`tests/architecture/test_f3_agent_health_port.py` — 10 tests:
consumo de `AGENT_HEALTH_PORT` (1), sin 8080 residual en el agente
(2,4), default documentado 8103 en launcher/`.env.example`/contrato (3),
frontend sigue en `8080` y compose sin 8103 (6), disjpación de puertos
(7) y **regresión runtime**: proceso real `python -m src.main` con
`AGENT_HEALTH_PORT` efímero responde `/health` en ese puerto — falla si
el agente vuelve a ignorar la variable (1/5).

## Validaciones (FASE 4)

`git diff --check` ✓ · YAML (ci/dependabot/secret-scanning/compose) ✓ ·
`docker compose config` ✓ · `bash -n start.sh stop.sh` ✓ ·
`ruff check .` ✓ · `mypy --config-file mypy.ini libs/` ✓ ·
`bandit -r apps/ libs/ -ll` rc=0 ✓ · `compileall apps libs` ✓ ·
F3 tests **10/10** ✓ · `pytest tests/` **776 passed** ✓ ·
`pytest tests/security tests/architecture` **331 passed** ✓ ·
tests existentes del agente **4 passed** ✓.
Frontend npm: sin cambios en `apps/web/` (solo doc `docs/`) → no aplica.

## Runtime verification (FASE 5)

- `./start.sh` (configuración normal, **con agente, sin --no-agent**):
  **rc=0** — `[start] linux-agent -> http://127.0.0.1:8103/health`
  `[ok] linux-agent healthy`; 12 servicios + gateway healthy; **0
  `EADDRINUSE`** (grep en logs = 0 para el agente).
- Frontend `127.0.0.1:8080` → **200**; agente `127.0.0.1:8103/health` →
  **200 JSON**; gateway → 200.
- `ss -ltnp`: `127.0.0.1:8080` = docker-proxy (frontend, **sin python**);
  `0.0.0.0:8103` = python pid del agente (mismo patrón de bind 0.0.0.0
  de los 12 servicios — preexistente, sin cambio de exposición).
- Ciclo **stop/restart**: `./stop.sh` ×2 → rc=0, `compose down` OK,
  volúmenes `docker_postgres_data`/`docker_redis_data` preservados (sin
  `-v`), 0 pidfiles, 8080/8103 libres; segundo boot rc=0 idéntico
  (reproducibilidad demostrada). Runtime restaurado al estado inicial
  (solo `docker-postgres-1`).
- Secretos en logs: **0** (grep de `REDIS_PASSWORD`/`JWT_SECRET_KEY`
  sobre `logs/`).

## Observación PRE-EXISTING / ENVIRONMENTAL (ajena a F3)

El agente responde `status: degraded` (`error_count` crece 1/ciclo,
`capture_count=0`): la credencial embebida en
`OBSERVATION_BUS_URL` (`.env`) **no coincide** con `REDIS_PASSWORD`
(empírico: `REDIS_PASSWORD`→PONG; credencial de la URL→`WRONGPASS`) →
`AuthenticationError` de publicación. El mismo drift explica
**411 `AuthenticationError` en `collector.log`** (línea 140856+) — el
data-plane de redis venía fallando antes de esta tarea. `.env` solo
recibió el bloque `AGENT_HEALTH_PORT`; no se tocó ninguna credencial
(regla: cambios mínimos trazables a F3). **Sin corregir aquí**
(RECOMMENDATION: alinear `OBSERVATION_BUS_URL`/`JWT_REDIS_URL` con
`REDIS_PASSWORD`).

## Compatibilidad Framework

Framework sin tocar (0 cambios, 0 escrituras en su journal); la decisión
`8103` es del Monitor (`cognitive_contract.md` es un artefacto del
producto, ADR-0002); Framework no define puertos (verificado FASE 1 y en
correccion_38).

## Limitaciones externas que permanecen (sin tocar)

Code scanning ausente · `secret_validity_checks` disabled · flags de
branch protection (`enforce_admins`/`dismiss_stale`/…) ·
`sha_pinning_required=false` · 0 tags de release · servicios host
`0.0.0.0` (LAN, observación preexistente) · drift de credencial redis
arriba · `stop.sh` conserva `|8080` en campo muerto (revisado, sin
cambio por FASE 2.3).

## Estado de commit/push

Sin commit y sin push (`AUTHORIZE_COMMIT`/`AUTHORIZE_PUSH` no presentes).
Contenido comercial: 0 · Secretos: 0 · SHAs futuros: 0 ·
journals históricos intactos · U6a/U6b/U7 intactos.
