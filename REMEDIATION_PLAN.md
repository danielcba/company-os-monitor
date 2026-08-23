# Plan de Remediación — Company OS Monitor
## Fases 1-3: Security → Scalability → Operations

**Fecha:** 2026-08-23
**Estado:** Pendiente de aprobación

---

## Fase 1: Critical Security (Semana 1-2)

### Tarea 1.1: JWT Token Revocation (C1)

**Problema:** Tokens comprometidos no se pueden invalidar. Refresh token (7 días) sin rotación.

**Solución:**
1. Agregar claim `jti` (UUID) a cada token en `libs/access/security.py`
2. Crear `libs/access/token_blacklist.py` — Redis-backed blacklist con TTL
3. Agregar `POST /api/v1/auth/logout` en user-service (blacklistear refresh token)
4. En gateway: verificar blacklist en `authenticate()` antes de decodificar
5. En user-service `refresh()`: blacklistear refresh token usado + emitir nuevo (rotación)

**Archivos a modificar:**
- `libs/access/security.py` — agregar `jti` claim, Método `create_token()` genera UUID
- `libs/access/token_blacklist.py` — **NUEVO**: `TokenBlacklist` class con Redis
- `apps/services/user-service/src/service.py` — logout(), refresh() con rotación
- `apps/services/user-service/src/health.py` — endpoint POST /auth/logout
- `apps/gateway/api-gateway/src/service.py` — verificar blacklist en authenticate()
- `.env.example` — agregar `JWT_REDIS_URL=redis://localhost:6379/1`

**Dependencias:** Redis ya está en docker-compose.yml ( puerto 6379)

**Esfuerzo:** 2 días

---

### Tarea 1.2: Report Service Auth (C2)

**Problema:** Report service (puerto 8098) completamente abierto. Sin JWT, sin RBAC, sin tenant isolation.

**Solución:**
1. Crear middleware compartido `libs/access/middleware.py` — `jwt_auth_middleware`
2. Aplicar middleware en report-service
3. Configurar JWT service en report-service main.py

**Archivos a modificar/crear:**
- `libs/access/middleware.py` — **NUEVO**: aiohttp middleware para JWT auth
- `apps/services/report-service/src/health.py` — registrar middleware
- `apps/services/report-service/src/main.py` — construir JwtService, pasar al server
- `apps/services/report-service/pyproject.toml` — agregar dependencia de `libs/access`

**Dependencias:** Tarea 1.1 (libs/access/security.py con jti)

**Esfuerzo:** 1 día

---

### Tarea 1.3: Distributed Rate Limiting (C3)

**Problema:** Rate limiter in-memory (se pierde en restart, no funciona multi-instance). Gateway sin rate limiting.

**Solución:**
1. Reescribir `RateLimiter` con Redis sorted sets (sliding window)
2. Agregar rate limiting al gateway (global + por endpoint)
3. Configurar límites por endpoint via env vars

**Archivos a modificar:**
- `apps/services/user-service/src/ratelimit.py` — Redis-backed implementation
- `apps/gateway/api-gateway/src/health.py` — agregar rate limiting
- `apps/gateway/api-gateway/src/main.py` — inicializar RateLimiter con Redis
- `.env.example` — `RATE_LIMIT_MAX_REQUESTS=10`, `RATE_LIMIT_WINDOW_SECONDS=60`

**Dependencias:** Tarea 1.1 (Redis connection compartida)

**Esfuerzo:** 1.5 días

---

### Tarea 1.4: Security Headers (C4 extra)

**Problema:** Zero security headers en toda la plataforma.

**Solución:**
1. Crear `libs/shared/security_headers.py` — aiohttp middleware
2. Agregar CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
3. Aplicar en gateway y user-service

**Archivos a crear/modificar:**
- `libs/shared/security_headers.py` — **NUEVO**: security headers middleware
- `apps/gateway/api-gateway/src/health.py` — registrar middleware
- `apps/services/user-service/src/health.py` — registrar middleware

**Dependencias:** Ninguna

**Esfuerzo:** 0.5 días

---

### Tarea 1.5: Gateway Service Discovery (C4)

**Problema:** Health checks hardcodeados a `localhost:PORT`. Fallará en K8s/cloud.

**Solución:**
1. Reemplazar `DEFAULT_SERVICE_HEALTH` con env var `GATEWAY_SERVICE_HEALTH`
2. Documentar formato: `collector=http://collector:8090/health,context=http://context:8091/health,...`
3. Validar que el parsing funcione correctamente

**Archivos a modificar:**
- `apps/gateway/api-gateway/src/service.py` — actualizar DEFAULT_SERVICE_HEALTH
- `apps/gateway/api-gateway/src/main.py` — mejorar _build_service_health()
- `.env.example` — agregar GATEWAY_SERVICE_HEALTH con formato documentado

**Dependencias:** Ninguna

**Esfuerzo:** 0.5 días

---

## Fase 2: Scalability & Reliability (Semana 3-5)

### Tarea 2.1: Parallel Tenant Processing (H1)

**Problema:** 7 servicios procesan tenants secuencialmente. Límite ~20-50 tenants.

**Solución:** Aplicar patrón `asyncio.gather` de ConfidenceService a los 7 servicios.

**Archivos a modificar:**
- `apps/services/context-service/src/service.py` — `run_activation_cycle()`
- `apps/services/pattern-service/src/service.py` — `run_detection_cycle()`
- `apps/services/anomaly-service/src/service.py` — `run_detection_cycle()`
- `apps/services/hypothesis-service/src/service.py` — `run_generation_cycle()`
- `apps/services/insight-service/src/service.py` — `run_restructure_cycle()`
- `apps/services/recommendation-service/src/service.py` — `run_recommendation_cycle()`
- `apps/services/decision-service/src/service.py` — `run_decision_cycle()`

**Patrón a seguir (de ConfidenceService):**
```python
await asyncio.gather(
    *[self._process_tenant(tid) for tid in tenants],
    return_exceptions=True,
)
```

**Dependencias:** Ninguna

**Esfuerzo:** 2 días (1 por servicio, 7 servicios)

---

### Tarea 2.2: N+1 Query Fix (H2)

**Problema:** RecommendationService hace `get_confidence()` por cada hypothesis (N queries).

**Solución:**
1. Agregar `list_confidence_by_hypothesis_ids()` en ConfidenceStore
2. Cargar todas las confidences de una vez por tenant
3. Crear dict `confidence_id → score` para lookup O(1)

**Archivos a modificar:**
- `libs/learning/confidence.py` — agregar método batch
- `apps/services/recommendation-service/src/service.py` — usar batch fetch

**Dependencias:** Ninguna

**Esfuerzo:** 1 día

---

### Tarea 2.3: Report Service Data Reuse (H3)

**Problema:** ReportService carga 10 stores × 3 report types = 30 queries secuenciales por tenant.

**Solución:**
1. Cargar `ReportSource` una vez por tenant
2. Reutilizar para los 3 report types

**Archivos a modificar:**
- `apps/services/report-service/src/service.py` — refactorizar run_report_cycle()

**Dependencias:** Ninguna

**Esfuerzo:** 0.5 días

---

### Tarea 2.4: Unify GracefulShutdown (H4)

**Problema:** confidence-service reimplementa GracefulShutdown localmente.

**Solución:**
1. Reemplazar implementación local con import de `libs/shared/graceful_shutdown.py`

**Archivos a modificar:**
- `apps/services/confidence-service/src/main.py` — importar de libs/shared

**Dependencias:** Ninguna

**Esfuerzo:** 0.5 días

---

### Tarea 2.5: Circuit Breakers (H5)

**Problema:** Sin protección contra cascade failures en DB.

**Solución:**
1. Crear `libs/shared/circuit_breaker.py` — circuit breaker con asyncio
2. Aplicar a todas las llamadas DB en stores

**Archivos a crear/modificar:**
- `libs/shared/circuit_breaker.py` — **NUEVO**: CircuitBreaker class
- Todos los stores en `libs/` — envolver calls en circuit breaker

**Dependencias:** Ninguna

**Esfuerzo:** 2 días

---

### Tarea 2.6: Distributed Tracing (H6)

**Problema:** Sin tracing distribuido. Debugging imposible.

**Solución:**
1. Crear `libs/shared/tracing.py` — OpenTelemetry setup
2. Instrumentar todos los servicios

**Archivos a crear/modificar:**
- `libs/shared/tracing.py` — **NUEVO**: tracing setup con OTel
- Todos los `main.py` de servicios — inicializar tracing
- `.env.example` — `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`

**Dependencias:** Ninguna

**Esfuerzo:** 2 días

---

### Tarea 2.7: Request Timeouts + Correlation IDs (H7)

**Problema:** Sin timeout por request, sin request ID para debugging.

**Solución:**
1. Crear `libs/shared/middleware.py` — timeout + correlation ID middleware
2. Aplicar en gateway y user-service

**Archivos a crear/modificar:**
- `libs/shared/middleware.py` — **NUEVO**: request_id + timeout middleware
- `apps/gateway/api-gateway/src/health.py` — registrar
- `apps/services/user-service/src/health.py` — registrar

**Dependencias:** Ninguna

**Esfuerzo:** 1 día

---

### Tarea 2.8: Collector Backpressure (H8)

**Problema:** Buffer in-memory ilimitado en collector.

**Solución:**
1. Agregar límite al buffer (max 1000 observations)
2. Bloquear cuando buffer lleno (backpressure)

**Archivos a modificar:**
- `apps/services/collector-service/src/consumer.py` — agregar límite

**Dependencias:** Ninguna

**Esfuerzo:** 0.5 días

---

## Fase 3: Operational Excellence (Semana 6-8)

### Tarea 3.1: Cloud-native Report Storage (H7)

**Problema:** Reports escritos a filesystem local.

**Solución:**
1. Crear `libs/shared/storage.py` — interfaz abstracta (S3/GCS/local)
2. Report service usa storage abstraction

**Archivos a crear/modificar:**
- `libs/shared/storage.py` — **NUEVO**: StorageBackend ABC + implementations
- `apps/services/report-service/src/service.py` — usar storage abstraction
- `.env.example` — `REPORT_STORAGE_BACKEND=local`, `REPORT_S3_BUCKET=...`

**Dependencias:** Ninguna

**Esfuerzo:** 2 días

---

### Tarea 3.2: Hot-reload Procedural Memory (H8)

**Problema:** Thresholds hardcoded en env vars. Sin hot-reload.

**Solución:**
1. Crear `libs/shared/config_watcher.py` — file watcher para config changes
2. Aplicar a anomaly, collector, decision services

**Archivos a crear/modificar:**
- `libs/shared/config_watcher.py` — **NUEVO**: ConfigWatcher class
- `apps/services/anomaly-service/src/service.py` — usar watcher
- `apps/services/collector-service/src/service.py` — usar watcher
- `apps/services/decision-service/src/service.py` — usar watcher

**Dependencias:** Ninguna

**Esfuerzo:** 1.5 días

---

### Tarea 3.3: Refactor Gateway Service.py (M3)

**Problema:** Gateway service.py es god object (466 líneas).

**Solución:**
1. Dividir en módulos por dominio
2. Mantener GatewayService como fachada

**Archivos a crear:**
- `apps/gateway/api-gateway/src/routes/decisions.py`
- `apps/gateway/api-gateway/src/routes/observations.py`
- `apps/gateway/api-gateway/src/routes/reports.py`
- `apps/gateway/api-gateway/src/routes/cognitive.py`
- `apps/gateway/api-gateway/src/routes/audit.py`

**Archivos a modificar:**
- `apps/gateway/api-gateway/src/service.py` — importar de módulos
- `apps/gateway/api-gateway/src/health.py` — usar módulos

**Dependencias:** Ninguna

**Esfuerzo:** 2 días

---

### Tarea 3.4: DB Latency in Health Checks (M6)

**Problema:** Health checks solo verifican error count, no DB latency.

**Solución:**
1. Agregar timing a `verify_connection()` en stores
2. Incluir DB latency en health endpoint

**Archivos a modificar:**
- `libs/shared/base_store.py` — agregar timing
- Todos los stores — mejorar verify_connection()

**Dependencias:** Ninguna

**Esfuerzo:** 1 día

---

### Tarea 3.5: Product state/project-state.md (E4)

**Problema:** Producto falta `state/project-state.md` para E4 compliance.

**Solución:**
1. Crear `state/project-state.md` con estado actual del producto

**Archivos a crear:**
- `state/project-state.md` — **NUEVO**: product state document

**Dependencias:** Ninguna

**Esfuerzo:** 0.5 días

---

### Tarea 3.6: CI/CD Pipeline

**Problema:** Sin pipeline automatizado.

**Solución:**
1. GitHub Actions con lint, typecheck, test, security scan

**Archivos a crear:**
- `.github/workflows/ci.yml` — **NUEVO**: CI pipeline

**Dependencias:** Ninguna

**Esfuerzo:** 1 día

---

### Tarea 3.7: OpenAPI Spec Generation (L1)

**Problema:** Sin spec de API automatizado.

**Solución:**
1. Auto-generar desde Pydantic models
2. Servir en `/openapi.json`

**Archivos a crear/modificar:**
- `libs/shared/openapi.py` — **NUEVO**: spec generator
- Todos los service main.py — agregar endpoint

**Dependencias:** Ninguna

**Esfuerzo:** 1 día

---

## Resumen de Esfuerzo

| Fase | Tareas | Esfuerzo Total |
|------|--------|----------------|
| **Fase 1: Security** | 5 | ~5.5 días |
| **Fase 2: Scalability** | 8 | ~10 días |
| **Fase 3: Operations** | 7 | ~9 días |
| **TOTAL** | 20 | **~24.5 días** |

---

## Dependencias entre Tareas

```
Fase 1:
  1.1 (JWT Revocation) → 1.2 (Report Auth)
  1.1 (JWT Revocation) → 1.3 (Rate Limiting)
  1.4 (Security Headers) → independiente
  1.5 (Service Discovery) → independiente

Fase 2:
  2.1 (Parallel Tenants) → independiente
  2.2 (N+1 Fix) → independiente
  2.3 (Report Reuse) → independiente
  2.4 (Unify Shutdown) → independiente
  2.5 (Circuit Breakers) → independiente
  2.6 (Tracing) → independiente
  2.7 (Timeouts + IDs) → independiente
  2.8 (Backpressure) → independiente

Fase 3:
  3.1 (Cloud Storage) → independiente
  3.2 (Hot-reload) → independiente
  3.3 (Refactor Gateway) → independiente
  3.4 (DB Latency) → independiente
  3.5 (Project State) → independiente
  3.6 (CI/CD) → independiente
  3.7 (OpenAPI) → independiente
```

---

## Archivos Nuevos a Crear

| Archivo | Propósito |
|---------|-----------|
| `libs/access/token_blacklist.py` | Redis-backed JWT blacklist |
| `libs/access/middleware.py` | Shared JWT auth middleware |
| `libs/shared/security_headers.py` | Security headers middleware |
| `libs/shared/circuit_breaker.py` | Circuit breaker for DB calls |
| `libs/shared/tracing.py` | OpenTelemetry setup |
| `libs/shared/middleware.py` | Request timeout + correlation ID |
| `libs/shared/storage.py` | Cloud storage abstraction |
| `libs/shared/config_watcher.py` | Hot-reload config watcher |
| `libs/shared/openapi.py` | OpenAPI spec generator |
| `.github/workflows/ci.yml` | CI/CD pipeline |
| `state/project-state.md` | Product state (E4) |

---

## Archivos a Modificar (Resumen)

### Fase 1 (Security)
- `libs/access/security.py` — jti claim
- `apps/services/user-service/src/service.py` — logout, refresh rotation
- `apps/services/user-service/src/health.py` — logout endpoint
- `apps/services/user-service/src/ratelimit.py` — Redis-backed
- `apps/services/report-service/src/health.py` — auth middleware
- `apps/services/report-service/src/main.py` — JWT service setup
- `apps/gateway/api-gateway/src/service.py` — blacklist check, service discovery
- `apps/gateway/api-gateway/src/health.py` — rate limiting, security headers
- `.env.example` — new config vars

### Fase 2 (Scalability)
- `apps/services/context-service/src/service.py` — asyncio.gather
- `apps/services/pattern-service/src/service.py` — asyncio.gather
- `apps/services/anomaly-service/src/service.py` — asyncio.gather
- `apps/services/hypothesis-service/src/service.py` — asyncio.gather
- `apps/services/insight-service/src/service.py` — asyncio.gather
- `apps/services/recommendation-service/src/service.py` — asyncio.gather, batch fetch
- `apps/services/decision-service/src/service.py` — asyncio.gather
- `apps/services/report-service/src/service.py` — data reuse
- `apps/services/confidence-service/src/main.py` — unified shutdown
- `apps/services/collector-service/src/consumer.py` — backpressure
- `libs/learning/confidence.py` — batch fetch method

### Fase 3 (Operations)
- `apps/services/report-service/src/service.py` — storage abstraction
- `apps/services/anomaly-service/src/service.py` — config watcher
- `apps/services/collector-service/src/service.py` — config watcher
- `apps/services/decision-service/src/service.py` — config watcher
- `apps/gateway/api-gateway/src/service.py` — refactor into modules
- `apps/gateway/api-gateway/src/health.py` — use route modules
- Todos los stores — DB latency in health checks
- Todos los main.py — tracing setup

---

## Riesgos y Mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Redis cae → rate limiting y blacklist no funcionan | Fallback a in-memory con warning en logs |
| asyncio.gather con muchos tenants → memory pressure | Limitar concurrencia con `asyncio.Semaphore` |
| Circuit breaker open → requests fallan | Configurar thresholds conservadores; alertas |
| Breaking changes en auth → frontend se rompe | Mantener backward compatibility; versionar API |
| OpenTelemetry overhead → performance impact | Sampling rate configurable; default 10% |

---

## Próximos Pasos

1. **Aprobar plan** — ¿Proceder con todas las fases o priorizar?
2. **Crear branch** — `feature/remediation-phase-1` para Fase 1
3. **Implementar incrementalmente** — commit por tarea
4. **Testing** — verificar que 169 tests siguen passing
5. **Update journal** — documentar cada cambio

---

## Decisiones del Usuario (2026-08-23)

1. **Alcance:** Todas las 3 fases completas
2. **Rate limiting:** Redis sorted sets (sliding window con ZRANGEBYSCORE)
3. **Tracing:** OpenTelemetry (estándar de la industria)
4. **Storage:** S3/GCS abstraction (fase 3)
5. **CI/CD:** GitHub Actions

## Próximos Pasos

1. Crear branch `feature/remediation-phase-1`
2. Implementar Fase 1 (Security) — tareas 1.1 a 1.5
3. Commit y push
4. Implementar Fase 2 (Scalability) — tareas 2.1 a 2.8
5. Commit y push
6. Implementar Fase 3 (Operations) — tareas 3.1 a 3.7
7. Commit y push
8. Verificar tests (169 passing)
9. Update journal + GitHub