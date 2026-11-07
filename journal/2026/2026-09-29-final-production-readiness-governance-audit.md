# 2026-09-29 — Final production readiness + governance audit (prompt `correccion_43.md`)

## Propósito

Auditoría FINAL de Production Readiness + Repository Governance sobre el
baseline publicado, en READ-ONLY: sin Sprint 13, sin commit
(`AUTHORIZE_COMMIT` no aparece YES), sin push, sin cambios de settings,
Framework = solo lectura. Clasificación de cada hallazgo con
FACT / OBSERVATION / EXTERNAL / RECOMMENDATION / BLOCKER y delimitación
final en categorías (RESOLVED / NON-BLOCKING EXTERNAL / PRE-EXISTING /
REQUIRES ARCHITECTURAL DECISION / HARDENING FOLLOW-UP / BLOCKER).

## Baseline (FASE 0 — verificado hoy con `git fetch --prune`)

- **Monitor**: `HEAD = origin/main = ls-remote =
  eb686e2ec5e06f8b9771e1a3dd56739ff6d631ce`; ahead/behind `0 0`;
  staged `0`; `git status --porcelain` = exactamente los 4 elementos
  preexistentes (ver abajo). Genealogía: U6A `7ca822d…`, U6B `079024e…`,
  U7 `65f528f…`, F3 `65223957…`, `3d18090…`, `e32fb88…` todos ancestros;
  **0 commits después del baseline**.
- **CI del baseline**: run `36596568927` (`CI`) re-verified hoy =
  `completed/success`, `headSha = eb686e2ec5e06f8b9771e1a3dd56739ff6d631ce`
  (jobs `lint-and-test (3.12, 24)` y `docker-build` = success).
- **Framework**: `381f56cfa48d092f85846e160d2e1fe6878f9f6f` =
  HEAD = origin/main = ls-remote; worktree con las **9 entradas
  preexistentes intactas** (4 M + 5 ??); `git status -- journal/` = 0
  escrituras; Framework journal = 0 escrituras. Framework escrito: NO.
- **Estado preexistente preservado y verificado al cierre**:
  ` M start.sh`, ` M stop.sh`,
  `?? journal/2026/2026-09-28-f3-agent-port-architectural-decision.md`,
  `?? journal/2026/2026-09-28-production-readiness-governance-audit.md`,
  `.env` gitignored (`.gitignore:24`) y fuera de Git. Nada staged.
- **Runtime preexistente**: solo `docker-postgres-1` al inicio y al
  cierre (restaurado tras los boots de la auditoría; estado final
  verificado: `Up (healthy)`, 0 procesos de servicio, puertos de gateway/
  usuario libres).

## Evidencia runtime (FASE 3)

- **3 ciclos boot→stop completados** en esta ejecución (2 completos + 1
  para el probe de CORS): los 14 servicios `healthy` en cada ciclo;
  persistencia básica verificada (tenants/evidence/observations se
  conservan entre ciclos); parada con SIGTERM + fallback SIGKILL a los
  20 s **por diseño** (`stop.sh:6-7,77-79`); en este ciclo 7 servicios
  excedieron los 20 s y usaron el fallback; `.runtime` eliminado;
  contenedores `Exited (0)`; estado final = solo postgres.
- **Loopback vigente**: compose publica `127.0.0.1:5433`,
  `127.0.0.1:6379`, `127.0.0.1:8080` (compose:12,24,39) — corrección
  D-01/loopback intacta.
- **Fail-closed confirmado**: `docker compose config` sin `.env` falla
  (`POSTGRES_PASSWORD`/`REDIS_PASSWORD` con `:?`); con env resuelve.
- **F9 (exposición LAN) re-confirmada en vivo**: los servicios de host
  bindean `0.0.0.0` → `http://192.168.100.64:8100/health` = **200** desde
  la IP LAN. Clase: REQUIRES ARCHITECTURAL DECISION (decisión de binding
  de host, fuera de esta auditoría).
- `stop.sh:29` declara `AGENT_HEALTH_PORT|8080` (frente a `8103` real en
  `start.sh:50` y `.env.example:216`): campo muerto en STOP_SPECS,
  cosmético, PRE-EXISTING — sin cambio.

## Hallazgo principal — CORS no funcional en gateway y user-service (**BLOCKER**)

- **Root cause (código)**: `GatewayServer.__init__` llama
  `self._setup_cors()` en `apps/gateway/api-gateway/src/health.py:64`
  **antes** de registrar rutas (rutas desde :68); ídem
  `apps/services/user-service/src/health.py:45`. El bucle
  `for route in self.app.router.routes()` (`health.py:592-593` y
  `:84-85`) itera **0 rutas** → la config CORS por ruta nunca se
  registra; el hook `on_response_prepare` (`cors_config.py:114,139`)
  no encuentra config → ningún header `Access-Control-*` se emite.
- **Evidencia curl (hoy, en vivo, con `Origin: http://localhost:8080`)**:
  - gateway `OPTIONS /api/v1/tenants/…/observations` → `405 Method Not
    Allowed`, `Allow: GET,HEAD`, sin `Access-Control-*`;
  - gateway `GET /health` → `200` **sin** `Access-Control-Allow-Origin`;
  - user-service `OPTIONS /api/v1/auth/login` → `405`, `Allow: POST`,
    sin `Access-Control-*`;
  - user-service `GET /health` → `200` sin `Access-Control-Allow-Origin`.
- **Evidencia browser (Firefox 156 headless, página de probe servida en
  `127.0.0.1:9999`, log con timestamps 17:11:28)**:
  - `PROBE_reach_reachable_type_opaque_status_0` → el gateway **sí es
    alcanzable** desde el browser (`fetch` no-cors resuelve);
  - `PROBE_auth_BLOCKED_TypeError: NetworkError when attempting to
    fetch resource.` → llamada API con `Authorization` (preflight) BLOQUEADA;
  - `PROBE_simple_BLOCKED_TypeError: NetworkError…` → `GET /health`
    simple también BLOQUEADO.
  La red funciona; **el fallo es exclusivamente de CORS**.
- **Divergencia test/producción (máscara)**: `tests/…/test_cors.py:30`
  construye su propia app con el orden **correcto** (comentario: "Routes
  must be registered BEFORE they are added to the CORS handler") →
  **5/5 passed** mientras el CORS real está inerte; ningún test ejercita
  el `GatewayServer`/`UserServer` real para CORS (`Access-Control` solo
  aparece en `test_cors.py` dentro de tests).
- **Historia**: introducido en `943ea8a` (2026-08-22) con el orden
  incorrecto desde su origen; `git log -S` no muestra otro mecanismo
  CORS en código de producción (nginx no tiene `proxy_pass`, ni CORS);
  la afirmación de `journal/2026/2026-08-19.md:51` de un preflight 204
  en vivo **no es reproducible** (probablemente refería una app de test).
- **Capa 2 del mismo defecto**: la allowlist efectiva default es solo
  `http://localhost:5173` (`health.py:577` / `:69`); `CORS_ALLOWED_ORIGINS`
  no está definido en `.env`, `.env.example` ni compose; la UI de
  producción corre en `:8080` y la SPA llama a `http://localhost:8100/api/v1`
  y `:8099` en absoluto (`apps/web/src/api/client.ts:4`) → con CORS
  correctamente cableado, el origen `:8080` igual quedaría fuera.
- **Impacto**: desde el browser, login y lecturas de API de la UI son
  imposibles (preflight rechazado → bloqueo del browser; lecturas sin
  ACAO → ilegibles). La política "CORS ALLOWED origin" del producto no
  se aplica nunca en runtime.
- **Clase**: **BLOCKER**. **Cambio mínimo propuesto (NO aplicado — FASE 7
  sin autorización de código)**: (1) mover `self._setup_cors()` detrás del
  registro de rutas en ambos `health.py`; (2) declarar
  `CORS_ALLOWED_ORIGINS` con `http://localhost:8080` en `.env.example`
  (allowlist explícita de la UI publicada); (3) test de integración que
  ejercite el `GatewayServer`/`UserServer` real (preflight con ACAO y
  simple GET con ACAO), cerrando la divergencia con `test_cors.py`.

## Otros hallazgos

- **Health `degraded` (insight/decision/recommendation/report), errors
  13→14** — PRE-EXISTING: side effect de `pytest tests/` sobre la DB
  persistente (`tests/_config.py` apunta a `localhost:5433`, no en memoria)
  con inserts raw SQL de `predicted_consequences` inválido
  (`tests/learning/test_h3_f01_f02_remediation.py:300,323`) →
  `ValidationError` de Pydantic; el health exige `errors==0`.
  **Disclosure**: esta ejecución ejecutó `pytest tests/` y añadió fixtures
  a la DB local (tenants 630→673, filas inválidas 13→14). Recomendación:
  aislar la DB de tests.
- **Collector `degraded`** = `TimeoutError` de `xreadgroup` en idle
  (`libs/cognitive_core/observation_bus.py:62-64`, ~5 s) — PRE-EXISTING
  desde 2026-08-28; los datos siguen fluyendo.
- **`decision.duplicates` creciente** = todas las recommendations quedan
  `proposed` (sin UPDATE por diseño) → reintento idempotente O(n) por
  ciclo — OBSERVATION, by design.
- Excepciones de `gather(return_exceptions=True)` contadas en silencio
  por servicios — OBSERVATION (HARDENING FOLLOW-UP: visibilidad).

## Governance (FASE 2 — lecturas API frescas hoy)

- **Branch protection (main)**: `enforce_admins=false`,
  `required_signatures=true`, `strict=true`, contexts
  `["lint-and-test (3.12, 24)","docker-build"]`,
  `approving_review_count=1`, `dismiss_stale=false`, `code_owner=false`,
  `last_push=false`, `restrictions=null`, rulesets=0.
- **CODEOWNERS** presente (`*`, `/adr/`, `/.github/workflows/`,
  `/libs/access/`, src de gateway y user-service).
- **Dependabot**: 19 entradas weekly (17 pip, 1 npm `/apps/web`, 1
  github-actions); alerts: **0 abiertas**, 1 `auto_dismissed` (undici,
  media). **Secret scanning**: enabled + push protection enabled;
  validity checks **disabled**; non-provider patterns **disabled**;
  0 alertas. **Code scanning**: 404 `no analysis found`;
  `default-setup state=not-configured`, `updated_at=null`; solo existe
  `.github/workflows/ci.yml` (sin workflow CodeQL) → causa verificable
  del 404, clase EXTERNAL. **Actions**:
  `default_workflow_permissions=read`, `allowed_actions=all`,
  `sha_pinning_required=false` (ci.yml sí pina los `uses` por SHA).
- **Tags**: 0 en Monitor y 0 en Framework; el Framework `.github` no
  define política release/tag → decisión humana pendiente.

## Validaciones (FASE 5 — sobre el estado exacto del baseline)

`git diff --check` PASS · `ruff check .` PASS · `mypy --config-file
mypy.ini libs/` = Success (70 source files) · `bandit -r apps/ libs/ -ll
-c bandit.yaml` exit 0 (High 0, Medium 0, Low 1767) · `python3 -m
compileall apps libs` OK · YAML 0 inválidos · `bash -n start.sh stop.sh`
OK · `pytest tests/` **778 passed** · `pytest tests/security
tests/architecture` **333 passed** · frontend: lint + typecheck OK y
**182 passed** · CI `36596568927` = success. Recuento de skips/xfails:
0/0 relevantes; sin errores de validación.

## Clasificación final (FASE 6)

- **BLOCKER**: 1 — CORS inerte en gateway y user-service (con capa 2 de
  allowlist) → la UI publicada no puede autenticar ni leer la API desde
  el browser.
- **REQUIRES ARCHITECTURAL DECISION**: 2 — (1) binding `0.0.0.0` de los
  servicios de host (F9, expuesto en LAN); (2) política release/tag
  (Framework y Monitor: 0 tags, sin política trackeada).
- **EXTERNAL**: 4 — code scanning/CodeQL no configurado; validity checks
  y non-provider patterns disabled; endurecimiento restante de branch
  protection (`enforce_admins`, `dismiss_stale`, `code_owner`,
  `last_push`); `allowed_actions=all` + `sha_pinning_required=false`.
- **RESOLVED**: Redis URL drift (3 URLs `redis://:` en `.env.example`;
  `.env` local también en forma `:clave`, 0 WRONGPASS hoy), F3
  (`AGENT_HEALTH_PORT=8103`), loopback ports, JWT placeholder gate.
- **PRE-EXISTING**: todo lo señalado arriba (health degraded por tests,
  collector idle timeout, `stop.sh:29` campo muerto, orden CORS desde
  `943ea8a`, SIGKILL fallback por diseño).
- **HARDENING FOLLOW-UP**: visibilidad de excepciones de `gather`;
  aislamiento de DB de tests; healthchecks de frontend en compose.

## Decisiones

1. **RELEASE BASELINE `eb686e2…`: NOT READY** — justificación factual:
   el producto publicado no puede usarse desde el browser contra su propia
   API (CORS inerte verificado por curl y por browser), y el fix mínimo
   requiere un cambio de código no autorizado en esta tarea.
2. Sin commit/push (autorizaciones no presentes); sin cambios de código;
   sin cambios de settings; sin Sprint 13.
3. El probe de CORS usó artefactos temporales fuera del repositorio
   (`/tmp/opencode/corsprobe/`), un archivo efímero en el contenedor
   frontend (eliminado con el ciclo) y procesos de Firefox diagnóstico
   posteriores limpiados (0 residuos al cierre). Repositorio sin ningún
   archivo nuevo salvo esta entrada.

## Limitaciones externas

- Habilitar code scanning, validity checks y endurecer branch protection
  / actions = GitHub human settings (EXTERNAL).
- Política release/tag = decisión humana (0 tags existentes).
- Esta auditoría no modificó código: el fix de CORS queda como propuesta
  mínima a ejecutar con autorización explícita.

## Estado de commit/push

`COMMIT: NOT CREATED` · `PUSH: NOT PERFORMED` — `AUTHORIZE_COMMIT` /
`AUTHORIZE_PUSH` no aparecen YES. Sin SHA nuevo (ninguno anticipado).
BASELINE PUBLICADA INTACTA: `eb686e2ec5e06f8b9771e1a3dd56739ff6d631ce`.
