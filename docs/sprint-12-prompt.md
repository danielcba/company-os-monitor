# SPRINT 12 — MULTI-TENANT + AUTH + RBAC (Decision Authority — Capacidad Externa, ADR-0002)

> Persistido desde sesión 2026-08-16. Sesión EVALUADA al inicio.

## Contexto de la sesión previa

- Sprints 1-5 (COMPLETOS): Perception completa + Pattern Detector. 128 tests.
- Sprint 6 (COMPLETO esperado): Anomaly Detector. `ANOMALY_HEALTH_PORT=8093`.
- Sprint 7 (COMPLETO esperado): Hypothesis Generator. `HYPOTHESIS_HEALTH_PORT=8094`.
- Sprint 8 (COMPLETO esperado): Confidence Calibration. `CONFIDENCE_HEALTH_PORT=8095`.
- Sprint 9 (COMPLETO esperado): Recommendation. `RECOMMENDATION_HEALTH_PORT=8096`.
- Sprint 10 (COMPLETO esperado): Decision. `DECISION_HEALTH_PORT=8097`. Gate cognitivo Q1 alcanzado. `authority_id` en `decisions` es UUID referenciado a user_id o policy_id (aún sin tabla de users).
- Sprint 11 (COMPLETO esperado): Report Generator. `REPORT_HEALTH_PORT=8098`.
- Infra corriendo: postgres TimescaleDB 127.0.0.1:5433 (db/user/pass = cosmonitor), redis 127.0.0.1:6379. Schema en `infrastructure/docker/init-sql/01-schema.sql` — NO tiene tablas de users/roles aún (se agregan en este sprint). La tabla `tenants` existe (id, name, slug UNIQUE, plan, settings, created_at, updated_at). Seed del tenant sandbox en 02-seed.sql.
- Marco cognitivo (SOLO LECTURA, no tocar): `/home/dcordoba/Documents/Default Project/company/company-os-main/`. Producto: `/home/dcordoba/Documents/Default Project/company-os-monitor/`.
- Documentación fuente del Sprint: concepto `Decision` del marco (`core-concepts/decision.md` — commitment authority), **ADR-0002** (auth/RBAC es capacidad externa no-canónica), **R3** (Cognitive Boundary — Perception/Reasoning nunca ejecutan acción sin autorización explícita), **P6** (Recommendation ≠ Decision, authority explícita). Diseño de producto: `docs/04-informes-seguridad.md` (FASE 7: Decision Authority & RBAC — roles viewer/operator/admin/superadmin mapeados a commitment authority; "RBAC no es 'permisos en BD' — es authority binding en Decision"), `docs/01-fundacion-arquitectura.md` (FASE 6: autenticación multi-tenant — "Input: Recommendation + Confidence → Transform: compromiso con authority → Output: Decision"), roadmap `docs/05-negocio-roadmap-backlog.md` (item #12 Multi-tenant + Auth + RBAC — "Authority binding para Decision").

### Correcciones de auditoría ya aplicadas (NO reintroducir)

- Citaciones canónicas: usar `P1`-`P7`, design rules `R1`-`R7`, conceptos del marco y ADR-0001/0002. NO inventar números de regla ni reciclar "R8/R9/R10". Trazabilidad/objetividad/provenance factual, sin número de regla. NO citar paths/specs inexistentes.
- Puertos/env: collector `HEALTH_PORT` (8090), context `ACTIVATOR_HEALTH_PORT` (8091), pattern `PATTERN_HEALTH_PORT` (8092), anomaly `ANOMALY_HEALTH_PORT` (8093), hypothesis `HYPOTHESIS_HEALTH_PORT` (8094), confidence `CONFIDENCE_HEALTH_PORT` (8095), recommendation `RECOMMENDATION_HEALTH_PORT` (8096), decision `DECISION_HEALTH_PORT` (8097), report `REPORT_HEALTH_PORT` (8098). El user-service usará `USER_HEALTH_PORT` (default 8099). NUNCA reutilizar nombres de env.
- **ADP-0002 governa**: auth/RBAC es capacidad EXTERNA no-canónica. Autoriza y protege el acceso al flujo canónico; NO produce juicios cognitivos. El RBAC se modela como **Decision Authority binding** (no como "tabla de permisos"): cada Decision registra quién/qué autorizó (authority_id). Los roles determinan qué authority puede ejecutar qué acción.
- **La autoridad NO ejecuta el pipeline**: el user-service valida identidad/rol y emite tokens; el decision-service (Sprint 10) ya registra el authority_id. Este sprint conecta ambos: los tokens llevan el rol → la autorización de una acción se valida contra el rol.
- `.env.example` ya tiene JWT vars (`JWT_SECRET_KEY`, `JWT_ALGORITHM=RS256`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS=7`) y de gateway (`TRAEFIK_DASHBOARD=true`). El `apps/gateway/api-gateway/` existe VACÍO.

## Objetivo

Implementar **multi-tenant + autenticación + RBAC** (capacidad externa no-canónica, ADR-0002): `user-service` (JWT, login/refresh, roles por tenant) + inicio del **API Gateway** (`api-gateway`) como enforcement del Cognitive Boundary (R3: Perception/Reasoning nunca ejecutan acción sin autorización explícita). Input: credenciales + tenant. Transform: verificar identidad, emitir token con rol y tenant. Output: tokens JWT firmados + autorización de las operaciones del pipeline según rol (viewer/operator/admin/superadmin) + `authority_id` conectado a las Decisiones del Sprint 10.

Regla conceptual que gobierna el sprint (concepto Decision + ADR-0002): **"Decisiones are the points where cognition meets the world... The commitment authority under which it was taken."** La autorización NO es un fin en sí: existe para que cada Decision/acción tenga un authority binding auditable y verificable (R5). El gateway enforza que los componentes del pipeline SOLO se llamen entre sí según el flujo canónico y que ninguna capacidad externa ejecute acción sin autorización.

## Entorno y comandos (OBLIGATORIO respetar)

- Instalación: `pip install --break-system-packages -e ".[dev]"` (Python 3.14 es externally-managed; `.venv` NO funciona; NO inicializar git).
- NO usar `cd` para ejecutar; usar workdir = raíz del repo. PYTHONPATH por-app:
  `PYTHONPATH="<ruta_app>:<repo_root>" python3 -m pytest <ruta_app/tests> -q`
  con `REPO="/home/dcordoba/Documents/Default Project/company-os-monitor"`.
- Correr TESTS EXISTENTES al final y dejarlos verdes (128 + Sprints 6-11).
- Ruff: reducir violaciones nuevas a cero salvo BLE001. line-length 100.
- Tests de integración con Postgres real: limpiar con `SET session_replication_role = replica` (superuser) y borrar explícitamente las filas hijas.
- `python-jose[cryptography]`, `passlib[bcrypt]`, `pyotp` ya están en `pyproject.toml` raíz — usarlos (NO agregar deps nuevas sin justificar).

## Proceso obligatorio (policy del marco)

- **Journaling (E6 / Directive 002)**: entry por sesión en `journal/YYYY/YYYY-MM-DD.md` con el formato del marco (`# Journal — YYYY-MM-DD (Sprint 12 — ...)` + secciones `## Theme`, `## Today's Progress`, `## Discoveries`, `## Decisions`, `## Reflection`, `## Quote of the Day`). Listar archivos cambiados.

## Entregables

1. **Schema: tablas de users/roles** (MODIFICAR `infrastructure/docker/init-sql/01-schema.sql` + migración idempotente):
   - `users`: id UUID PK, tenant_id FK → tenants (aislamiento multi-tenant), email VARCHAR UNIQUE, password_hash TEXT (bcrypt), name VARCHAR, role VARCHAR(20) (viewer/operator/admin/superadmin), is_active BOOLEAN DEFAULT TRUE, created_at, updated_at. Índice `idx_users_tenant_email(tenant_id, email)`.
   - `refresh_tokens` (opcional, si se persiste) o solo JWT stateless con refresh en Redis (documentar decisión).
   - Migración idempotente `infrastructure/db-migrations/sprint12-users-tables.sql` para BDs previas + APLICAR a la BD existente. El seed (`02-seed.sql`) puede agregar un admin para el tenant sandbox (password de desarrollo documentado) — JUSTIFICAR y documentar.
   - Los `decisions.authority_id` (Sprint 10) ahora pueden referenciar `users.id` reales. NO romper la tabla decisions (authority_id queda como UUID libre; user-service garantiza consistencia de quien emite tokens).

2. **user-service** (`apps/services/user-service/` — el directorio existe VACÍO; crear completo):
   - Estructura: `src/main.py`, `src/service.py`, `src/health.py`, `src/auth/`, `tests/`, `pyproject.toml`, `Dockerfile`.
   - `src/auth/security.py`: hash/verify bcrypt (passlib), JWT emit/verify (python-jose, RS256 — documentar clave; para dev puede ser HS256 con `JWT_SECRET_KEY`, en prod RS256), acceso/refresh tokens con expiración.
   - `src/auth/rbac.py`: roles y permisos — el RBAC mapea a **Decision Authority** (docs/04): viewer (READ de contexto/recommendations/decisions/reports; NO propose/commit/execute), operator (+ACK decision), admin (READ + PROPOSE recommendation + COMMIT decision en tenant con risk_tolerance low/medium + define políticas automatizadas), superadmin (todo + cross-tenant + high risk). Constantes puras, testeadas.
   - Endpoints: `POST /api/v1/auth/login` (email+password → access+refresh), `POST /api/v1/auth/refresh`, `POST /api/v1/users` (crear user en tenant, solo admin/superadmin), `GET /api/v1/me` (perfil+rol), `GET /api/v1/users` (listado tenant). TODOS con aislamiento por tenant (un user solo ve su tenant).
   - `src/service.py`: `AuthService` (verify credentials, emit tokens, refresh, autorizar acción por rol). Métricas `/metrics`: `total_logins`, `total_login_failures`, `total_tokens_issued`, `total_errors`, `users_by_role`.
   - Puerto: `USER_HEALTH_PORT` (default 8099).
   - R1 (externo, ADR-0002): user-service NO implementa capacidad cognitiva del pipeline; autentica/autoriza.

3. **API Gateway** (`apps/gateway/api-gateway/` — el directorio existe VACÍO; iniciar su contenido):
   - MVP: gateway FastAPI/aiohttp que valida tokens (verify JWT), extrae tenant+rol, y enruta a los servicios del pipeline. NO reimplementa la lógica cognitiva: es **Cognitive Boundary enforcement** (R3).
   - Middleware de boundary (documentado en docs/04 `cognitive_boundary.yaml`): 
     - perception_to_reasoning: solo flujo Evidence → Context; raw observations NUNCA expuestas a Reasoning/Action.
     - reasoning_to_action: solo Recommendation (con Confidence) → Decision; Pattern/Anomaly/Hypothesis NUNCA gatillan alertas/acciones directas; el gateway valida presencia de confidence (R4).
     - action_execution: ejecución requiere authority binding (rol del token); todas las ejecuciones se loguean (audit_log, futuro).
   - En el MVP el gateway expone rutas READ sobre los datos del pipeline (para report-service/dashboard futuro) protegidas por rol, y la validación de que una acción tipo "commit" requiera rol con permiso.
   - El gateway PUEDE quedar como servicio ligero que valida y reenvía; documentar qué rutas reales del pipeline expone (health de servicios, reports, decisions listado).

4. **Tests** (unit + integración PG):
   - Security: login con password correcto → tokens; password incorrecto → rechazado; refresh válido/inválido; token con rol/tenant correctos; token vencido → rechazado.
   - RBAC: matriz roles×permisos — viewer NO puede propose/commit; operator NO commit; admin SI commit low/medium; superadmin commit high + cross-tenant (assert por cada celda).
   - Multi-tenant: user del tenant A NO accede a datos del tenant B (aislamiento por tenant_id en queries).
   - Gateway: request sin token → 401; con token viewer intentando commit → 403; con token admin commit → permitido (mock de los servicios).
   - ADR-0002: el gateway/user-service NO producen juicios cognitivos (test de que no hay lógica de pipeline en auth/rbac — solo autorización).
   - Integración PG: INSERT user, read-back, hash no es plaintext; password verificación.
   - Regresión: TODAS las suites previas verdes (128 + Sprints 6-11 + nuevas).

5. **Docs/env**: README (sección Sprint 12 + cómo correr + nota ADR-0002/R3), `.env.example` (verificar/agregar `USER_HEALTH_PORT=8099`, `GATEWAY_HEALTH_PORT=8100`, JWT vars ya existentes; documentar). Journal al cierre. NO modificar prompts previos ni journal previo.

## Cumplimiento cognitivo a validar al cerrar

- ADR-0002: auth/RBAC y gateway son externos no-canónicos — autorizan, no razonan; NUNCA bypassan el flujo.
- R3: Cognitive Boundary enforced por el gateway (Perception/Reasoning no ejecutan acción sin autorización explícita; el gateway valida).
- R5: toda decisión queda con authority binding verificable (authority_id de un user real del tenant); traza completa.
- P6: Recommendation ≠ Decision; authority explícita (rol) para commit; viewer/operator no pueden commitar.
- Multi-tenant: aislamiento estricto por tenant_id en users y en el acceso del gateway.
- R4: el gateway valida que las acciones tipo Recommendation→Decision llevan Confidence (integra con Sprints 8-10).
- Cierra el bloque Q1 (Cognitive Core): pipeline completo + autoridad + boundary. El siguiente bloque es H1 (Sprint 13+: Insight, calibración histórica, Procedural Memory v2, patrones avanzados).
- No avanzar a Insight (Sprint 13), patrones/anomalías avanzadas (Sprints 16-17) ni LM Studio (Sprint 18).

## Criterios de aceptación verificables

- pytest verde: 128 + Sprints 6-11 + nuevos del user-service / gateway / auth / rbac.
- Corriendo `user-service` contra la PG real: login del admin sandbox → access token; acceso a `/api/v1/me` con token → perfil+rol; request sin token → 401; viewer no commitea (403); admin commitea.
- Tablas `users`/roles creadas en la BD con la migración; seed admin del tenant sandbox funcional.
- Aislamiento multi-tenant verificado (user A no ve tenant B).
- `decisions.authority_id` referenciable a users reales (consistencia).
- Re-corrida sin duplicados (dedup probado en el service); `decisions` y demás tablas cognitivas sin cambios espurios.
- Métricas en `:8099/metrics` (user-service con `USER_HEALTH_PORT=8099`) y gateway en `:8100` (`GATEWAY_HEALTH_PORT=8100`).
