# 2026-09-29 — Cierre del BLOCKER CORS (prompt `correccion_44.md`)

## Baseline real (FASE 0, verificado con `git fetch --prune`)

- Monitor: `HEAD = origin/main = ls-remote =
  eb686e2ec5e06f8b9771e1a3dd56739ff6d631ce`, ahead/behind `0 0`,
  staged `0`. CI del baseline: run `36596568927` = `success`
  (re-verify al inicio). Estado preexistente local preservado
  (` M start.sh`, ` M stop.sh`, journals `??` c37/c38 y el journal de la
  auditoría previa, `.env` gitignored).
- Framework: `381f56cfa48d092f85846e160d2e1fe6878f9f6f` = HEAD =
  origin/main = ls-remote; 9 entradas preexistentes intactas; journal del
  Framework = 0 escrituras. `FRAMEWORK MODIFIED: NO`.
- U6A `7ca822d…`, U6B `079024e…`, U7 `65f528f…`, F3 `6522395…` intactos
  (ancestros del baseline; sin cambios en esta tarea).

## Blocker y causa raíz (verificada sobre el código real, FASE 3)

`GatewayServer.__init__` ejecutaba `self._setup_cors()` ANTES de registrar
rutas (`apps/gateway/api-gateway/src/health.py`), e ídem `UserServer`
(`apps/services/user-service/src/health.py`). El bucle
`for route in self.app.router.routes()` recorría **0 rutas** → la
configuración por ruta de `aiohttp_cors` nunca se registraba → ningún
header `Access-Control-*` se emitía → preflight `405` y `GET/health` 200
sin ACAO. La allowlist por defecto (`http://localhost:5173`) tampoco
incluía el origin del frontend publicado (`http://localhost:8080`) y
`CORS_ALLOWED_ORIGINS` no existía en `.env.example`. `test_cors.py`
probaba una app sintética con el orden correcto por lo que no detectó la
regresión.

## Cambios exactos (FASE 4 — mínimos, sin ampliar alcance)

1. `apps/gateway/api-gateway/src/health.py`: `self._setup_cors()` movido
   detrás del último `router.add_*` (una línea movida; cero cambios de
   semántica, cero cambios de auth/JWT/middleware).
2. `apps/services/user-service/src/health.py`: mismo movimiento detrás del
   último `router.add_*`.
3. `.env.example`: nueva declaración
   `CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8080`
   con comentario que documenta la fuente única de verdad (la variable ya
   leída por ambos servicios en `_setup_cors`; no se introdujo una segunda
   fuente). `CORS_ALLOWED_ORIGINS` NO estaba declarada antes en el
   template.

NO modificado: `.env` versionado (no existe en Git), Framework, U6A/U6B/U7,
F3, Redis, workflows, start.sh/stop.sh (hunks preexistentes intactos),
settings remotos.

Nota de validación local: se añadió `CORS_ALLOWED_ORIGINS` al `.env`
LOCAL (gitignored, no versionado) exclusivamente para la validación live
de esta tarea, según lo permitido para validación temporal.

## Tests añadidos/cambiados (FASE 5)

- `apps/gateway/api-gateway/tests/test_cors.py`: se MANTIENEN los 5 tests
  legacy (app sintética) y se añaden **7 tests de integración contra la
  app REAL `GatewayServer`** (preflight con origin permitido, GET simple
  con ACAO exacta, ruta protegida 401 con ACAO, origin denegado sin
  política (GET y preflight), sin Origin sin cabeceras, origin Vite
  permitido). El preflight real es el detector de la regresión "CORS
  antes de registrar rutas".
- `apps/services/user-service/tests/test_cors.py` (nuevo): **7 tests
  contra la app REAL `UserServer`** — preflight de login, login cruzado
  exitoso legible, 401 legible con ACAO, GET simple con ACAO, origin
  denegado sin política, sin Origin sin cabeceras, origin Vite.
- **Detección demostrada (mutación transitoria, revertida)**: reinstalar
  el orden histórico en el gateway hizo fallar 5 de los 7 tests reales
  con exactamente el síntoma de producción (`405 Allow: GET,HEAD` y
  `KeyError: Access-Control-Allow-Origin`); con el fix, 12/12 gateway +
  7/7 user-service en verde.

## Evidencia curl (FASE 6, servicios reales en vivo, origin `http://localhost:8080`)

- Gateway `OPTIONS /api/v1/tenants/…/observations` → **200** +
  `Access-Control-Allow-Origin: http://localhost:8080` +
  `Allow-Methods: GET` + `Allow-Headers: AUTHORIZATION`.
- Gateway `GET /health` → **200 + ACAO**; `GET …/observations` sin token →
  **401 + ACAO** (auth intacta, respuesta legible).
- Gateway origin denegado: GET → **200 SIN ACAO**; preflight → **403**.
  Sin Origin → **0 headers CORS**.
- User-Service `OPTIONS /api/v1/auth/login` → **200 + ACAO** +
  `Allow-Methods: POST` + `Allow-Headers: CONTENT-TYPE`; `GET /health` →
  **200 + ACAO**; origin denegado → preflight **403**, GET sin ACAO.
- Login real con credenciales válidas + Origin → **200 + ACAO +
  access_token**.

## Evidencia browser (FASE 6 — mismo mecanismo que la auditoría previa)

Página servida por el frontend publicado en `http://localhost:8080`
(script externo, CSP `script-src 'self'` cumplido), Firefox 156 headless,
reporte por `fetch` a `localhost:9999` (permitido por `connect-src`):

- `PROBE_start_script_running_origin_http://localhost:8080`
- `PROBE_login_type_cors_status_200_token_yes`
- `PROBE_apiread_type_cors_status_200_total_423`
- `PROBE_gwhealth_type_cors_status_200`
- `PROBE_usrhealth_type_cors_status_200`
- `PROBE_done_all_settled` (sin entradas `BLOCKED`)

`type_cors` en cada `response` es la validación CORS del propio browser
(un fallo CORS lanza `TypeError` en lugar de resolver). Login cruzado y
lectura API autenticada funcionan desde el browser. Artefactos del probe
(contenedor, perfil Firefox, listener) eliminados al cierre.

## Resultados de validación (FASE 7 — estado final exacto)

- `git diff --check` PASS · `ruff check .` PASS (1 I001 auto-corregido en
  el test nuevo) · `mypy --config-file mypy.ini libs/` = Success (70
  files) · mypy gateway `src/` y user-service `src/` (forma de CI) =
  Success (22 y 8 files) · `bandit -r apps/ libs/ -ll` exit 0
  (High 0, Medium 0, Low 1812; los 2 archivos de test nuevos aportan 54
  Low por credenciales de test hardcodeadas, mismo patrón que los tests
  existentes) · `compileall` OK · YAML 0 inválidos · `bash -n` OK.
- `pytest tests/` = **778 passed** · `pytest tests/security
  tests/architecture` = **333 passed** · gateway suite = **158 passed,
  1 skipped** · user-service suite = **62 passed** · CORS específicos =
  12 + 7 passed · frontend: lint OK, typecheck OK, vitest **182 passed**.
- Observación (no bloqueo, diseño preexistente de tests): las corridas de
  `pytest` sobre la DB persistente local (`localhost:5433`) añadieron
  fixtures — tenants 673 → 770, evidence → 432, observations → 1746 —
  mismo side effect documentado en auditorías previas. Se creó además un
  usuario local de validación `cors-validation@local.test` (rol viewer,
  tenant `…0001`) para el login browser; sin credenciales registradas en
  ningún archivo versionado.
- Smoke/runtime: stack completo boot `start_rc=0`,14 servicios healthy,
  matriz CORS live (arriba), comportamiento sin Origin y con origin
  denegado verificado en vivo.

## Seguridad del fix (FASE 8)

- Sin `Access-Control-Allow-Origin: *` en fuentes (grep); responses de
  origin permitido llevan SOLO el origin exacto de la lista.
- Origins arbitrarios: no; lista explícita localhost:5173 + localhost:8080
  (mínima — con ella el flujo browser completo funcionó, no se requirió
  política más amplia).
- Origin denegado no obtiene ACAO ni `Allow-Credentials` (tests + curl
  en vivo: GET sin cabeceras, preflight 403).
- Auth intacta: 401 sin token conservado con ACAO legible; login sigue
  exigiendo credenciales; CSRF/JWT/middleware sin tocar.
- Sin secretos en archivos versionados (grep sobre el diff).

## Limitaciones restantes

- `stop.sh:29` conserva el campo muerto `AGENT_HEALTH_PORT|8080`
  (cosmético, preexistente — fuera de alcance).
- Temas separados de `correccion_43` sin tocar (branch protection,
  CodeQL, validity checks, bind `0.0.0.0`, release/tag, DB de tests,
  non-root, digests).
- El journal de la auditoría previa
  `2026-09-29-final-production-readiness-governance-audit.md` queda
  intacto y sin commitear (estado preexistente preservado).

## Commit / CI

Referencias al commit y a la CI de este cambio se registran en el reporte
de cierre (POST-verificación remota), no aquí: este journal forma parte
del commit único y ningún SHA se anticipa (FASE 10).
