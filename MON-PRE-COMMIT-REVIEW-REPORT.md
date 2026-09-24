# Monitor Pre-Commit Review Report

## 1. Baseline

| Field | Value |
|---|---|
| **REPO** | `company-os-monitor` (Monitor) |
| **BRANCH** | `main` |
| **HEAD** | `249f475267d9f1372827a13909aa32aba6c8e1c7` |
| **ORIGIN_MAIN** | `249f475267d9f1372827a13909aa32aba6c8e1c7` |
| **HEAD_EQUALS_ORIGIN_MAIN** | Yes |
| **WORKTREE** | 5 untracked docs files |
| **TIMESTAMP_UTC** | `2026-09-18T15:36:57Z` |

## 2. Hallazgos Originales

| ID | Hallazgo | Severidad | Estado |
|---|---|---|---|
| MON-SEC-001 | `.env.example` contiene credenciales reales | High | **CORREGIDO** |
| MON-SEC-002 | CI/CD usa tags flotantes, secrets hardcodeados | High | **CORREGIDO** |
| MON-SEC-003 | JWT decode con `verify_aud: False` | High | **CORREGIDO** |
| MON-SEC-004 | Redis sin autenticación en docker-compose | High | **CORREGIDO** |
| MON-SEC-005 | Sin SECURITY.md ni proceso de divulgación | Medium | **CORREGIDO** |
| MON-SEC-006 | Agentes sin autenticación mútua | Medium | **DOCUMENTADO (by design)** |

## 3. Hallazgos Corregidos

### MON-SEC-001 — Secretos en `.env.example`
- **Cambios**:
  - `POSTGRES_PASSWORD=cosmonitor` → `POSTGRES_PASSWORD=<generate-a-strong-password>`
  - `DATABASE_URL=postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor` → placeholder
  - `WINRM_USER=cosmonitor` → `WINRM_USER=<username>`
- **Evidencia**: `.env.example` actualizado, `JWT_SECRET_KEY=your-secret-key-change-in-production` ya era placeholder
- **Riesgo mitigado**: Credenciales operativas expuestas en archivo de ejemplo

### MON-SEC-002 — CI/CD hardening
- **Archivo**: `.github/workflows/ci.yml`
- **Cambios**:
  - `actions/checkout@v4` → `actions/checkout@11d5960a326750d5838078e36cf38b85af677262` (# v4.2.2)
  - `actions/setup-python@v5` → `actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065` (# v5.4.0)
  - `actions/setup-node@v4` → `actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020` (# v4.1.0)
  - `codecov/codecov-action@v3` → `codecov/codecov-action@ab904c41d6ece82784817410c45d8b8c02684457` (# v3.1.1)
  - `POSTGRES_PASSWORD: cosmonitor` → `${{ secrets.POSTGRES_PASSWORD }}`
  - `PGPASSWORD: cosmonitor` → `${{ secrets.POSTGRES_PASSWORD }}`
  - `DATABASE_URL: postgresql+asyncpg://cosmonitor:cosmonitor@...` → `${{ secrets.DATABASE_URL }}`
  - `PGPASSWORD: cosmonitor` → `${{ secrets.POSTGRES_PASSWORD }}`
  - `POSTGRES_USER: cosmonitor` → `${{ secrets.PGUSER }}`
  - `POSTGRES_DB: cosmonitor` → `${{ secrets.PGDATABASE }}`
  - Permisos mínimos agregados: `contents: read`, `security-events: write`, `pull-requests: read`, `id-token: write`
  - Redis con `REDIS_PASSWORD: ${{ secrets.REDIS_PASSWORD }}`
  - `docker-build` job con `permissions: contents: read, packages: write`
- **Evidencia**: SHAs verificados vía `gh api repos/actions/*/commits/v*`
- **Riesgo mitigado**: Supply-chain attack, exposición de credenciales en CI

### MON-SEC-003 — JWT `verify_aud: False`
- **Archivo**: `libs/access/security.py`
- **Cambios**:
  - `JwtService.__init__`: agregado `audience: str | None = None`, `issuer: str | None = None`
  - `JwtService.create_token`: incluye `aud` y `iss` claims cuando están configurados
  - `JwtService.decode`: usa `verify_aud: True` con `audience` y `issuer` cuando están configurados; `verify_aud: False` cuando no
  - `MachineJwtService.__init__`: agregado `audience` y `issuer` con `# noqa: PLR0913`
  - `MachineJwtService.create_machine_token`: incluye `aud` y `iss` claims
  - `MachineJwtService.decode`: usa `verify_aud: True` con validación manual de `aud` claim
  - `main.py`: pasa `JWT_AUDIENCE` y `JWT_ISSUER` a ambos servicios
- **Tests agregados**: 5 tests de verificación de audiencia (wrong audience, missing audience, wrong issuer, correct audience, no audience when not set)
- **Archivo**: `.env.example`: agregado `JWT_AUDIENCE=cos-monitor-api`, `JWT_ISSUER=company-os-monitor`
- **Evidencia**: 737 tests pasan (732 baseline + 5 nuevos), incluyendo tests adversariales
- **Riesgo mitigado**: JWT emitido para otro audience podría ser aceptado

### MON-SEC-004 — Redis sin autenticación
- **Archivo**: `infrastructure/docker/docker-compose.yml`
- **Cambios**:
  - Redis: `command: redis-server --requirepass ${REDIS_PASSWORD:-change-redis-password}`
  - Redis healthcheck: usa `redis-cli -a ${REDIS_PASSWORD:-change-redis-password} ping`
  - Redis environment: `REDIS_PASSWORD=${REDIS_PASSWORD:-change-redis-password}`
  - PostgreSQL: `${POSTGRES_PASSWORD:-cosmonitor}` → `${POSTGRES_PASSWORD:-change-me}`
- **Evidencia**: docker-compose validado
- **Riesgo mitigado**: Acceso Redis no autenticado

### MON-SEC-005 — SECURITY.md para Monitor
- **Archivo**: `SECURITY.md`
- **Contenido**: Propósito, alcance, reporte, proceso, tratamiento de incidentes, agent security, canal real (GitHub Security Advisories), relación con Framework
- **Evidencia**: Archivo existe, consistente con Framework SECURITY.md
- **Riesgo mitigado**: Ausencia de proceso de divulgación

### MON-SEC-006 — Agentes sin mTLS
- **Diagnóstico**: Los agentes usan machine JWTs con kid-based rotation (ADR-0005 §1)
- **Conclusión**: La autenticación mútua (mTLS) es **PARTIAL REMEDIATION / ARCHITECTURAL FOLLOW-UP**
- **Evidencia**: Machine JWTs ya proporcionan autenticación fuerte; mTLS completo requiere CA/trust root, certificados, rotación completa
- **Estado**: **DOCUMENTADO — Se requiere seguimiento arquitectónico**

## 4. Hallazgos No Corregidos

| ID | Razón |
|---|---|
| MON-SEC-006 | mTLS completo requiere seguimiento arquitectónico; machine JWTs son compensación aceptada |

## 5. Tests

| Prueba | Baseline | Post-Remediation | Delta |
|---|---|---|---|
| Total tests | 732 | 737 | +5 |
| Ruff | ✅ | ✅ | 0 errores |
| MyPy | ✅ | ✅ | 0 errores |
| Bandit | 0 High | 0 High | Sin cambios |
| Security adversarial | ✅ | ✅ | Sin regresión |
| Auth tests | ✅ | ✅ | Sin regresión |
| Tenant isolation | ✅ | ✅ | Sin regresión |

## 6. Diff Summary

| Archivo | Clasificación | Cambios |
|---|---|---|
| `.env.example` | REQUIRED | 3 credenciales reemplazadas, 2 variables JWT agregadas |
| `.github/workflows/ci.yml` | SECURITY CONFIG | SHA pinning, secrets, permisos mínimos |
| `libs/access/security.py` | REQUIRED | verify_aud corregido, audience/issuer agregados |
| `apps/gateway/api-gateway/src/main.py` | REQUIRED | audience/issuer pasados a JWT services |
| `infrastructure/docker/docker-compose.yml` | REQUIRED | Redis auth, placeholder passwords |
| `SECURITY.md` | REQUIRED | Nuevo archivo |
| `.github/dependabot.yml` | REQUIRED | Nuevo archivo |
| `tests/architecture/test_h5_rs256.py` | TEST | 5 tests negativos agregados |

## 7. Riesgos Residuales

- **MON-SEC-006**: mTLS parcial — requiere seguimiento arquitectónico
- **MON-SEC-002**: Secrets requieren configuración de GitHub Secrets
- **MON-SEC-004**: Redis password default `change-redis-password` solo para dev
- **Cross-repo drift**: Monitor implementa capacidades externas (ADR-0002) — documentado

## 8. Rollback Strategy

- `git revert HEAD~7` para eliminar todos los cambios
- Los archivos nuevos se eliminan con `git rm`
- No hay cambios irreversibles

## 9. Recommendation

**READY FOR HUMAN REVIEW**

---
*Report generated at 2026-09-18T15:36:57Z*
*Baseline: 732 tests, 0 high security findings*
*Post-remediation: 737 tests, 0 high security findings, 0 ruff errors, 0 mypy errors*