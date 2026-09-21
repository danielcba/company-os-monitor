# 2026-09-21 — D-01 Credential Remediation Closure + Gateway Test Collection Fix

## Objetivo

Cierre documental de D-01 credential remediation y remediación del fallo de
colección de tests del Gateway (ModuleNotFoundError: tests._config).

## Baseline

- **HEAD**: `d7717d055dcaf09ddac347ec632c7e7247c0f59e`
- **origin/main**: `d7717d055dcaf09ddac347ec632c7e7247c0f59e`
- **Branch**: `main`
- **Latest CI**: 35625053278 — SUCCESS

### Commits relevantes (cronológico)

| SHA | Message | Scope |
|-----|---------|-------|
| `e3d5a5c` | security: close D-01 credential remediation | 44 files: all services, gateway, libs, tests, CI, docker-compose |
| `00acd1b` | fix(ci): add tests package initializer | 1 file: tests/__init__.py |
| `b594b12` | fix(tests): remove service-local test package shadowing | 11 files: removed __init__.py from service test dirs |
| `f18deff` | fix: restore ruff import ordering after tests package cleanup | 13 files: import reordering in service tests |
| `d7717d0` | fix: remediate gateway test collection failure | 1 file: test_cognitive_trace.py |

## D-01 — Credential Remediation

### Alcance de e3d5a5c

La remediación D-01 cerró completamente la exposición de credenciales
de producción en el código fuente:

- **libs/shared/db.py**: `DATABASE_URL` desde env, `RuntimeError` si falta
  (fail-closed). Sin fallback a `cosmonitor:cosmonitor`.
- **Todos los service main.py** (12 servicios + gateway):
  `os.getenv("DATABASE_URL")` → `RuntimeError` si no está definido.
- **tests/_config.py**: Centraliza `TEST_DATABASE_URL` para tests de
  integración. Fallback a `cosmonitor:cosmonitor` solo en contexto de test.
- **tests de cada servicio**: Importan `from tests._config import TEST_DATABASE_URL`.
- **.env.example**: Placeholder explícito `REPLACE-WITH-A-UNIQUE-SECRET-KEY`
  para `JWT_SECRET_KEY`. Sin valores reales.
- **docker-compose.yml**: Credenciales de ephemeral containers para CI.
- **security regression tests**: `tests/security/test_d01_failclosed.py`
  verifica fail-closed en db.py, service main.py, y absence de hardcoded
  credentials en .env.example y código.

### Estado D-01

```
FULLY CLOSED — verificado por tests/security/test_d01_failclosed.py (101/101 PASS)
```

## Gateway Test Collection Fix

### Fallo original

- **CI run**: 35537678372
- **Commit probado**: `f18deffa8f2514fe0766b3f901e972e5f106cfe6`
- **Error**: `ModuleNotFoundError: No module named 'tests._config'`
- **Archivo**: `apps/gateway/api-gateway/tests/test_cognitive_trace.py:32`
- **Step**: Gateway tests

### Causa raíz

`apps/gateway/api-gateway/tests/__init__.py` (presente desde initial commit)
hace que Python resuelva `tests` al paquete local del Gateway en lugar del
paquete raíz `tests/` (que contiene `_config.py`). El import
`from tests._config import TEST_DATABASE_URL` falla porque el paquete
local no tiene `_config.py`.

Esto es independiente del problema de Ruff I001 (ordering) corregido en
`f18deff`.

### Cadena de remediación

1. `00acd1b` — Agregó `tests/__init__.py` raíz (necesario para que
   `tests._config` sea importable como paquete).
2. `b594b12` — Eliminó `tests/__init__.py` de 11 servicios para resolver
   package shadowing (los servicios resolvían `tests` a su directorio local
   en lugar de la raíz).
3. `f18deff` — Corrigió import ordering (Ruff I001) tras la eliminación
   de `__init__.py` en servicios.
4. `d7717d0` — Corrigió el fallo del Gateway eliminando la dependencia de
   `tests._config` y usando `os.getenv("DATABASE_URL")` directamente.

### Fix applied (d7717d0)

```python
# ANTES (fallo):
from tests._config import TEST_DATABASE_URL
DSN = TEST_DATABASE_URL

# DESPUÉS (corregido):
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL not set", allow_module_level=True)
DSN = DATABASE_URL
```

- Sin credenciales hardcodeadas
- Comportamiento equivalente cuando `DATABASE_URL` está definido (CI)
- Skip explícito cuando no está definido (entorno local sin DB)

## Validación

### Test Results (verificados localmente)

| Suite | Passed | Failed | Notes |
|-------|--------|--------|-------|
| Root | 737 | 0 | |
| Security | 101 | 0 | Incluye D-01 regression tests |
| Architecture | 191 | 0 | |
| Gateway | 168 | 0 | Sin collection errors |
| Services (12) | 462 | 0 | anomaly(56) collector(39) confidence(41) context(33) decision(53) evaluation(49) hypothesis(22) insight(3) pattern(43) recommendation(36) report(32) user(55) |

**Nota**: Las suites se solapan parcialmente (root incluye security y
architecture). El total agregado de invocaciones separadas es 1659, pero
no son 1659 tests únicos.

### Ruff

```
All checks passed (0 errors, I001 = 0)
```

### CI

```
Run 35625053278: SUCCESS
lint-and-test (3.12, 24): PASSED
docker-build: PASSED
```

## Limitaciones Documentadas

1. **Dockerfiles** (12 archivos): Contienen `cosmonitor:cosmonitor` como
   default de build-time. Clasificados como LOW risk (CI/Docker-only,
   overridden by compose env). No corregidos en esta tarea — follow-up
   de bajo prioridad.

2. **insight-service**: `tests/__init__.py` presente (desde initial commit
   `0be8241`). Genera el mismo problema de shadowing que Gateway tuvo antes
   del fix. Tests de insight-service pasan (3/3) porque no importan
   `tests._config`, pero la dependencia de resolución está rota.
   Follow-up pendiente.

3. **Root test flakiness**: `test_n_samples_cardinality[2]` falla
   intermitentemente por DB state contention entre tests. Pasa cuando se
   ejecuta aislado. Pre-existente, no relacionado con cambios de esta serie.

## Archivos Afectados (por esta serie de commits)

### e3d5a5c (D-01)
- 44 archivos: servicios, gateway, libs, tests, CI, docker-compose

### 00acd1b
- `tests/__init__.py` (nuevo)

### b594b12
- 11 `tests/__init__.py` eliminados de servicios

### f18deff
- 13 archivos de tests de servicios (import ordering)

### d7717d0
- `apps/gateway/api-gateway/tests/test_cognitive_trace.py`

## state/project-state.md

Verificado: contenido actual es factual y preciso.
- P1-P7: 7/7 — correcto
- R1-R7: 7/7 — correcto
- Security: JWT + rate limiting + CSP — correcto
- Architecture: 12 services + gateway + user-service — correcto

**No se requiere modificación.**

## Estado Final

- Commit `d7717d0` publicado en `main` y `origin/main`
- CI GREEN (run 35625053278)
- Working tree: solo 10 untracked pre-existentes
- Journal entry creado
- Framework: SIN MODIFICACIONES
- Framework journal: SIN MODIFICACIONES
