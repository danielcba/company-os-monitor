# Release Governance + Architectural Decision Audit — 2026-09-29

## Baseline

- Monitor: `446dd36f6c74b99958261e33a5bc073a632ee1f4` (parent `eb686e2ec5e06f8b9771e1a3dd56739ff6d631ce`), `HEAD = origin/main = ls-remote`, ahead/behind `0 0`, staged `0`.
- CI del baseline: run `36636544200` (`CI`), head `446dd36…`, `completed/success`; jobs `lint-and-test (3.12, 24)` = success y `docker-build` = success.
- Framework: `381f56cfa48d092f85846e160d2e1fe6878f9f6f` triple-match,0 writes al journal del Framework.
- Estado preexistente preservado: ` M start.sh`, ` M stop.sh`, `??` tres journals de auditorías anteriores (sin tocar), `.env` local gitignored.

## Objetivo

Auditoría y cierre de las decisiones arquitectónicas / de gobernanza externas
quedaron documentadas como no-blocking tras el cierre del CORS blocker
(`446dd36…`). Solo lectura: sin commit, sin push, sin settings, sin tags.

## D1 — Host services bind `0.0.0.0`

**Situación actual (FACT).** Los14 servicios/agentes del host se ejecutan como
procesos Python en el host (`start.sh` → `python -m src.main`), no en
contenedores, y todos hacen `web.TCPSite(runner, "0.0.0.0", port)`:

| Servicio | Puerto | Env var | Consumidor real |
|---|---|---|---|
| collector | 8090 | `HEALTH_PORT` | gateway `service.py` (`http://localhost:8090/health`) |
| context (activator) | 8091 | `ACTIVATOR_HEALTH_PORT` | gateway (`localhost:8091`) |
| pattern | 8092 | `PATTERN_HEALTH_PORT` | gateway (`localhost:8092`) |
| anomaly | 8093 | `ANOMALY_HEALTH_PORT` | gateway (`localhost:8093`) |
| hypothesis | 8094 | `HYPOTHESIS_HEALTH_PORT` | gateway (`localhost:8094`) |
| confidence | 8095 | `CONFIDENCE_HEALTH_PORT` | gateway (`localhost:8095`) |
| recommendation | 8096 | `RECOMMENDATION_HEALTH_PORT` | gateway (`localhost:8096`) |
| decision | 8097 | `DECISION_HEALTH_PORT` | gateway (`localhost:8097`) |
| report | 8098 | `REPORT_HEALTH_PORT` | gateway (`localhost:8098`) |
| user | 8099 | `USER_HEALTH_PORT` | navegador (`client.ts` → `localhost:8099`) + gateway |
| gateway | 8100 | `GATEWAY_HEALTH_PORT` | navegador (`client.ts` → `localhost:8100`) + probes `start.sh` |
| insight | 8101 | `INSIGHT_HEALTH_PORT` (default en código; **no declarada en `.env.example`**) | probes `start.sh` |
| evaluation | 8102 | `EVALUATION_HEALTH_PORT` | probes `start.sh` |
| linux-agent | 8103 | `AGENT_HEALTH_PORT` | probes `start.sh` (`127.0.0.1:8103`) |

**Evidencia runtime (FACT).** Con el stack levantado (`start.sh` rc=0,14
procesos `src.main`):
- `ss -ltn`: `0.0.0.0:8090` … `0.0.0.0:8103` (14 listeners) y
  `127.0.0.1:8080` (contenedor frontend, publicación loopback).
- Reachability desde la IP no-loopback del host (`192.168.100.64`):
  `8100 → HTTP 200`, `8099 → 200`, `8103 → 200`; `8080 → REFUSED`.
  Loopback contrast: `8080/8100/8099 → 200`.
  → la exposición LAN de los servicios del host es REAL; el frontend NO es
  accesible desde LAN (perímetro loopback desde `e32fb88 security: restrict
  compose published ports to loopback`).

**Categorías (FACT).**
- A (accesibles exclusivamente por host/local): los14 — todo consumidor
  verificado está en el mismo host y habla `localhost` (gateway
  `service.py:89-98`, `client.ts:4,6`, probes `start.sh` usando `127.0.0.1`).
- B (legítimamente más allá de loopback): **vacío hoy**. El único argumento
  futuro es despliegue de agentes fuera del host (windows/vmware-agent
  conceptualmente remotos) o acceso de operador desde otra máquina — hoy no
  soportado (el propio frontend es loopback-only).

**Clasificación: `ARCHITECTURAL DECISION`.** Cambio mínimo propuesto (NO
aplicado; requiere autorización y decisión de topology de despliegue):
`127.0.0.1` o `HOST` env configurable en los16 `TCPSite`. La corrección CORS
(`localhost:8080`) y el compose publicado no se regresaron.

## D2 — Release / tag policy

**Hechos (FACT):**
- `git ls-remote --tags` = `0`; `git tag` local = `0`; API `releases` = `0`;
  API `tags` = `0`. Sin evidencia de convención previa de tags en `git log`.
- Un solo workflow: `.github/workflows/ci.yml`; sin pasos de
  `upload-artifact`/release/publish (solo Codecov informational,
  `fail_ci_if_error` deliberado).
- Versionado divergente: raíz/user-service `pyproject.toml` = `0.1.0`;
  `apps/web/package.json` = `0.0.0` (placeholder Vite). Sin CHANGELOG, sin
  LICENSE detectada (API license → 404, `license: null`).
- Rama por defecto `main`, repo público, no archivado;30 ramas (main +
  dependabot/*).

**Clasificación:** `FACT` (estado) + `REQUIRES EXPLICIT DECISION` (si el
producto requiere tags/releases/policy documental o su ausencia es
deliberada). No inventar política. No crear tags ni releases.

## GitHub governance (lectura actual, sin modificar)

**Branch protection `main` (FACT):**
- `required_status_checks`: `strict=true`, contexts
  [`lint-and-test (3.12, 24)`, `docker-build`] — coinciden con los jobs reales
  del run `36636544200` (success).
- `required_pull_request_reviews`: `required_approving_review_count=1`;
  `dismiss_stale_reviews=false`; `require_code_owner_reviews=false`;
  `require_last_push_approval=false`.
- `required_signatures.enabled=true`, `enforce_admins.enabled=false`;
  `allow_force_pushes=false`; `allow_deletions=false`.
- `rulesets=[]` (sin rulesets).

**OBSERVACIÓN (governance remota, `EXTERNAL`):** con `enforce_admins=false`,
las reglas no aplican al propietario-admin: los commits de este historial
llegan a `main` por push directo y la API devuelve `verification: null` /
`signed:false` en `446dd36`, `eb686e2`, `6522395`, `65f528f` pese a
`required_signatures=true` — consistente con el aviso histórico
`Bypassed rule violations`, evidencia de gobernanza remota que NO se
reinterpreta como fallo de código. No modificable desde esta tarea.

**Code scanning (FACT):** CodeQL NO configurado. Causa exacta: solo existe el
workflow `ci.yml` (sin workflow CodeQL) y el default setup no está activado
(code-scanning API → `no analysis found`). Habilitarlo requiere
`EXTERNAL`/settings del propietario (prohibido aquí).

**Secret scanning (FACT):** `enabled`; `push_protection=enabled`;
`validity_checks=disabled` (`EXTERNAL`); `non_provider_patterns=disabled`;
0 alerts. Config propia `.github/secret_scanning.yml` con `paths-ignore`
(docs, adr, journal, .env.example, node_modules, .venv*, .opencode).

**Actions policy (FACT):** repo `allowed_actions=all`,
`sha_pinning_required=false` (settings `EXTERNAL`); el workflow cumple
least-privilege por decisión propia: `permissions: contents: read` (global y
por job), actions pineadas a SHA completo con comentario de versión
(`checkout`, `setup-python`, `setup-node`, `codecov`) y
`persist-credentials: false` en ambos checkouts;
`default_workflow_permissions=read`, `can_approve_pull_request_reviews=false`.
CODEOWNERS `* @danielcba` + rutas críticas (adr, workflows, access, gateway,
user-service).

## Observaciones adicionales

- `OBSERVATION` — `bandit.yaml` justifica el skip B104 con "bind0.0.0.0
  *inside their containers* / gobernado por la red de compose", pero los
  servicios corren en el HOST: la justificación documental está desactualizada
  (no cambia el comportamiento de bandit). `RECOMMENDATION`: actualizar el
  comentario al resolver D1.
- `OBSERVATION` — `INSIGHT_HEALTH_PORT` (8101) no está declarada en
  `.env.example` aunque la leen `insight-service/src/main.py` y `start.sh`.

## Limitaciones

- E2E de navegador NO re-ejecutado en esta auditoría: sin cambios de código
  desde el cierre de CORS (HEAD inalterado); la revalidación se hizo con la
  matriz curl real en el mismo SHA (preflight200+ACAO, GET200+ACAO,
 401+ACAO, login preflight200+ACAO+POST, origen denegado sin ACAO,
  sin `ACAO: *`).
- El test LAN usó la IP no-loopback de la propia máquina (evidencia de
  interfaz, no un segundo dispositivo físico).
- El aviso `Bypassed rule violations` es evidencia histórica documentada; los
  endpoints rule-suites devuelven404 en este repo y no se re-deriva vía API.
- Ningún setting de GitHub fue modificado; ningún archivo de código fue
  modificado; sin commit/push (sin `AUTHORIZE_*`).

## Decisiones pendientes (humanas/externas)

1. D1: topology de bind (loopback vs LAN) para los14 servicios del host.
2. D2: política de tags/releases/versionado documental (o ausencia deliberada).
3. `secret_scanning_validity_checks` (hoy disabled).
4. CodeQL / code scanning (hoy no configurado).
5. Ajustes de branch protection (`enforce_admins`, dismiss stale, last-push
   approval, review count) — settings del propietario.

## Validaciones ejecutadas

- Baseline triple-match `446dd36…`, staged `0`, preexistente intacto.
- Framework triple-match `381f56cf…`, journal0 writes.
- Ancestors: U6A `7ca822d…`, U6B `079024e…`, U7 `65f528f…`, F3/Redis
  `6522395…` y fix Redis `eb686e2…` — todos intactos.
- `AGENT_HEALTH_PORT=8103` en `.env.example` y `.env` local.
- `.env` untracked + gitignored; contenido comercial ausente.
- CORS revalidado PASS en runtime (ver Limitaciones).
