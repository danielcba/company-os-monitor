# Estrategia de Backup — Company OS Monitor

**Estado:** Activo (módulo estrella de confiabilidad)
**Aplica a:** `company-os-monitor` (el producto)

---

## 1. Objetivo

Garantizar la **confianza garantizada** ("100% de confiabilidad") sobre los
datos vitales de la plataforma: que ante cualquier fallo (hardware, corrupción,
error humano, desastre), la plataforma pueda recuperarse sin pérdida de
información canónica.

Este módulo de backup es una capacidad **externa no-canónica** (ADR-0002):
no participa en el pipeline cognitivo, solo protege el estado persistente.

---

## 2. Datos vitales

| Dato | Store | Naturaleza |
|---|---|---|
| Observaciones, evidencia, contextos, patrones, anomalías, hipótesis, confianza, decisiones, reportes | **PostgreSQL 16** | Canónico (append-only, P1) |
| Memory Ledger (aprendizaje, P7) | **PostgreSQL 16** | Canónico |
| Streams de observaciones, blacklist JWT, rate-limit | **Redis 7** | Transitorio (reconstruible) |
| Reportes generados (PDFs/JSON) | **Disco local** (`REPORT_OUTPUT_DIR`) | Artefactos |

---

## 3. Mejores prácticas implementadas

1. **Regla 3-2-1**: 3 copias, 2 medios distintos, 1 fuera de sitio (off-site).
2. **Cifrado en reposo**: cada artefacto se cifra con **AES-256** (`openssl
   enc -aes-256-cbc -pbkdf2`) antes de escribirse.
3. **Point-In-Time Recovery (PITR)**: se soporta archivado de WAL de PostgreSQL
   para restaurar a cualquier minuto (no solo al último full backup).
4. **Backup lógico** (`pg_dump -Fc`): portable, permite restaurar a otro
   cluster/versión.
5. **Verificación de restauración** (`verify_restore.py`): el único sello de
   "confianza garantizada" es que un backup se puede restaurar. Se prueba con
   `pg_restore --list`.
6. **Manifiesto de integridad**: SHA-256 de cada artefacto (detección de
   corrupción/tampering).
7. **Retención**: rotación diaria/semanal/mensual (por defecto 14 días).

---

## 4. Estructura del módulo

```
libs/storage/backup/
  __init__.py      # principios (documentación)
  backup.py        # primitivas: cifrado, manifiesto, PG/Redis
  orchestrator.py  # corrida completa (dump → cifrar → manifiesto → retención)
scripts/backup/
  run_backup.py    # CLI del backup
  verify_restore.py # verificación de restauración
```

---

## 5. Uso

```bash
export BACKUP_PASSPHRASE="$(openssl rand -hex 32)"   # guardar en lugar seguro
python3 scripts/backup/run_backup.py \
    --root backups \
    --passphrase "$BACKUP_PASSPHRASE" \
    --db-password "$POSTGRES_PASSWORD" \
    --redis-password "$REDIS_PASSWORD" \
    --artifacts reports-output \
    --retention-days 14
```

**Verificación de restauración:**
```bash
python3 scripts/backup/verify_restore.py \
    --backup backups/backup-YYYYmmdd-HHMMSS \
    --passphrase "$BACKUP_PASSPHRASE"
```

---

## 6. Programa sugerido (cron)

- **Diario 02:00**: backup completo (PG + Redis + artefactos), cifrado.
- **Diario 03:00**: verificación de restauración del backup de ayer.
- **Semanal**: copia off-site (objeto storage separado).
- **Mensual**: snapshot de retención larga.

---

## 7. Recuperación ante desastres (DRP) — resumen

1. Levantar un PostgreSQL vacío (mismo major version).
2. Descifrar `postgres.dump.enc` → `pg_restore` (o restaurar basebackup físico
   + WAL para PITR).
3. Restaurar artefactos descifrados.
4. Redis se reconstruye (streams + blacklist se repueblan o se aceptan vacíos).
5. Verificar health de todos los servicios.

---

## 8. Garantías y limitaciones

- La **confianza garantizada** se logra con: cifrado + manifiesto + verificación
  de restauración + regla 3-2-1.
- La **PITR** requiere configurar WAL archiving (paso de producción) — el módulo
  ya soporta el basebackup físico, listo para ese paso.
- El cifrado depende de la **passphrase**; si se pierde, los backups son
  irrecuperables. Guardarla en un gestor de secretos.
