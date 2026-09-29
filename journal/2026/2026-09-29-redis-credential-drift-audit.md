# 2026-09-29 — Redis credential drift audit (prompt `correccion_41.md`)

## Baseline real (FASE 0, verificado con `git fetch --prune`)

- Monitor: `HEAD = origin/main = ls-remote =
  652239576400ed1cf6e2b8f5925408cbba3e9db7`, ahead/behind 0/0, staged 0.
- CI baseline: run `36495563542` sobre ese SHA = `success` (2/2 jobs).
- Framework: `381f56cfa48d092f85846e160d2e1fe6878f9f6f` = HEAD = ls-remote;
  9 entradas preexistentes intactas; Framework journal = 0 escrituras.
- U6a `7ca822d…`, U6b `079024e…`, U7 `65f528f…` = ancestros de HEAD ✓.
- Estado preexistente verificado y preservado: ` M start.sh` (hunk redis
  c37), ` M stop.sh` (+11 carga `.env`, c37), journals c37/c38 `??`.
- Runtime preexistente: solo `docker-postgres-1`; `:6379`/`:8080`/`:8103`
  libres.

## Motivo

Cerrar la `RECOMMENDATION` de correccion_39: `Redis credential drift in
.env`. Auditoría inicialmente READ-ONLY (`AUTHORIZE_COMMIT=NO`,
`AUTHORIZE_PUSH=NO`); corrección de repositorio solo si resultaba
necesaria, segura y estrictamente relacionada.

## Definición exacta del supuesto drift (FASE 1)

Hipótesis previa (c39): credencial embebida en `OBSERVATION_BUS_URL`
distinta de `REDIS_PASSWORD`. Verificación por comparación booleana +
fingerprints sha256 (sin imprimir valores):

- `REDIS_PASSWORD` (36 chars) == userinfo de `REDIS_URL` ==
  userinfo de `OBSERVATION_BUS_URL` == userinfo de `JWT_REDIS_URL`:
  **IGUALES** (mismo fingerprint) → **no hay dos credenciales distintas**.
- El `.env` es internamente coherente. `DATABASE_URL` incrusta
  `POSTGRES_PASSWORD` (también IGUALES).

El drift real es de **formato, no de valor**: las URLs usan
`redis://<clave>@host` (userinfo **sin `:`**), que redis-py (8.1.0, igual
en CI `redis==8.1.0` y en `.venv` del collector) interpreta como
**username** con password vacía → handshake `HELLO … AUTH <clave> ""` →
Redis con `--requirepass` responde **WRONGPASS**
(`invalid username-password pair`).

## Evidencias (FASE 2/4/5)

- **Matriz de fuentes**: compose → `--requirepass ${REDIS_PASSWORD:?}`
  (fail-closed, fuente operativa); healthcheck compose y `start.sh:214`
  usan `redis-cli -a "$REDIS_PASSWORD"` (correcto); normalización de
  `start.sh` (líneas 112-134) preserva el userinfo y solo reescribe el
  host (verificado con forma `:clave` y sin `:`); `.env.example` prescribe
  el formato sin `:` en comentario y en las 3 URLs (desde el commit
  inicial `65387be`, 2026-08-18); consumidores: collector/agente/
  windows/vmware → `OBSERVATION_BUS_URL`; gateway/user/report →
  `JWT_REDIS_URL`; `REDIS_URL` sin consumidor en `apps/`/`libs/`
  (solo normalización/CI/tests). Dockerfiles y defaults de código usan
  URLs **sin credencial** (`redis://redis:6379`, `redis://localhost:6379`)
  → NOAUTH (fail-closed), fuera del alcance de este drift. CI usa
  `redis://localhost:6379/0?password=…` (estilo que redis-py sí parsea
  como password — verificado), coherente y sin cambios.
- **Timeline**: `requirepass` entró en compose el 2026-09-19
  (`e3d5a5c`); el collector no corrió entre esa fecha y el 2026-09-28
  (última ejecución previa: 2026-08-28); el primer
  `AuthenticationError` del `collector.log` es 2026-09-28 17:04:49 (boot
  ajeno a c39) y hubo **800 WRONGPASS** (17:04–17:08 y 18:00–18:11, los
  boots de c39). El defecto quedó oculto hasta el primer arranque con
  collector + requirepass.
- **Runtime (FASE 5, redis real levantado con el mismo interpolation que
  start.sh y restaurado después)**:
  a) credencial correcta → `PONG` (aceptada);
  b) credencial incorrecta → `WRONGPASS` (rechazada);
  c) sin credencial → `NOAUTH` (fail-closed);
  d) `CONFIG GET requirepass` del contenedor == `REDIS_PASSWORD`:
    **IGUAL** (fuente de verdad operativa confirmada);
  e) cliente real del collector (`.venv`, redis-py 8.1.0) con la URL
    actual (sin `:`) → `AuthenticationError (WRONGPASS)` — reproducción
    del fallo de runtime;
  f) misma URL y misma clave con forma `redis://:<clave>@localhost:6379`
    → `PING OK`;
  g) estilo CI `?password=` con la misma clave → `PING OK`.
  Restauración: contenedor redis eliminado, `docker-postgres-1` intacto,
  `:6379` libre. `.env` NO alterado (tests en memoria; mtime sin cambios).

## Framework (FASE 3)

`.github` trackeado del Framework solo contiene `workflows`; no existe
política trackeada de secretos/formato de credenciales (los conceptos de
`cognitive-lexicon` mencionan credenciales solo como ejemplos de
Recommendation/Hypothesis). El Monitor decide en su dominio (ADR-0002);
no se requiere decisión de arquitectura nueva: la fuente de verdad es
determinable (`REDIS_PASSWORD`) y la forma corregida es la documentada
por redis-py. Framework NO modificado; su journal NO modificado.

## Clasificación (FASE 4)

**C — REPOSITORY CONFIGURATION DRIFT.**
No es A/B (el template publicado prescribe un formato que rompe AUTH);
no es D (una misma credencial en todos lados, sin bypass, sin
exposición, fallo **cerrado**: WRONGPASS/NOAUTH, no fail-open); no es E
(la fuente de verdad está claramente determinada y verificada).

## Fuente de verdad

1. **Valor**: `REDIS_PASSWORD` en `.env` (interpolado por compose a
   `--requirepass` y verificado igual al `requirepass` en vivo).
2. **Formato de URL**: la forma documentada por redis-py
   `redis://:<clave>@host[:port][/db]` (password tras dos puntos).

## Cambios realizados (FASE 7 — locales, sin commit)

1. `.env.example`: las 3 URLs Redis pasan a `redis://:…@…` y el comentario
   de la línea 9 documenta la forma y el motivo (username-position →
   WRONGPASS). Mínimo: solo template y su comentario.
2. `tests/security/test_redis_url_format.py` (nuevo): fija que toda URL
   Redis con credencial del template parsea como **password** (y no como
   username) con redis-py, y prohíbe el patrón `redis://sin-dos-puntos@`.
3. `tests/security/test_d01_failclosed.py`: +1 método que fija que la
   normalización de host de `start.sh` preserva la forma `:clave`, y
   docstring de la clase actualizado a la forma canónica (los tests
   legacy de forma sin `:` se conservan: los `.env` locales existentes
   deben seguir normalizando).

**NO modificados**: `.env` local (gitignored, recomendación aparte),
`start.sh`/`stop.sh` (hunks c37 intactos byte a byte), compose, código,
workflows, Framework, U6a/U6b/U7.

## Validaciones (FASE 8)

`git diff --check` OK · `ruff check .` OK · YAML/compose config OK ·
`bash -n start.sh stop.sh` OK · test nuevo **1 passed** ·
`test_d01_failclosed` **25 passed** ·
`tests/security tests/architecture` **333 passed** ·
`pytest tests/` **778 passed** · secretos en diff **0** ·
staged **0**.

## Decisión final

Template corregido y garantizado con tests; runtime demostrado (a–g);
`.env` local queda con el formato legacy hasta que su propietario aplique
el mismo cambio de formato (una `:` por URL) — no se tocó por regla.

## Limitaciones externas

- El `.env` local sigue en formato sin `:` (recomendación siguiente,
  fuera del repo); cualquier `.env` ya copiado del template anterior
  comparte el defecto.
- Defaults credentialless en Dockerfiles/código (NOAUTH si se usan sin
  env) — sin cambio, fuera del alcance.
- Comentario de `start.sh:115` y docstring legacy describen la forma sin
  `:` como caso histórico — dejados intactos (cambio no necesario).
- Code scanning/secret_validity/branch protection: sin cambios
  (preexistentes).

## Estado de commit/push

`COMMIT: NOT CREATED` — `AUTHORIZE_COMMIT=NO`, `AUTHORIZE_PUSH=NO`.
Sin SHA nuevo (ninguno anticipado). BASELINE PUBLICADA INTACTA:
`652239576400ed1cf6e2b8f5925408cbba3e9db7`.
