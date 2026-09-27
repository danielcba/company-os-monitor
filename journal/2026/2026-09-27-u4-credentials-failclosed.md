# 2026-09-27 — U4 Credentials fail-closed (prompt `correccion_18.md`)

## Objetivo

Publicar la unidad **U4 — Credentials fail-closed** (prioridad P1 —
security/correctness) del Release Hardening auditado en `correccion_08`:
impedir el uso accidental de credenciales placeholder provenientes de
`.env.example`, manteniendo comportamiento fail-closed, sin exponer secretos
reales y sin alterar issuer/audience (U3), tenant isolation, blacklist/Redis
ni machine auth.

## Baseline

- **Monitor HEAD / origin/main / ls-remote**: `a27988b016811c792d50b6a1c5fe67390c195ec0`
  (`fix: wire report service jwt issuer and audience` = U3, publicada con CI
  run `36276186483` completed/success).
- **divergence**: ahead = 0, behind = 0. **working tree**: 33 M + 4 ?? = 37
  entradas; índice real = 0 staged.
- **Framework**: `381f56cfa48d092f85846e160d2e1fe6878f9f6f` == origin/main,
  0 staged, 9 entradas, journal intacto.

## Alcance de la unidad (6 paths)

1. `.env.example` — `REDIS_PASSWORD`/URLs con credencial (Redis corre con
   requirepass → docker exige la variable, fail-closed) + comentarios que
   marcan `JWT_SECRET_KEY=REPLACE-WITH-…` como plantilla que JwtService
   rechaza. Sin secretos reales.
2. `libs/access/security.py` — `_PLACEHOLDER_MARKERS` (`REPLACE-WITH`,
   `CHANGE-ME`, `YOUR-SECRET-KEY-CHANGE-IN-PRODUCTION`, `...`),
   `_PLACEHOLDER_EXACT` (`changeme`, `change-me`, …), `_reject_placeholder`
   (no eco el valor; nombra la variable y la remediación `openssl rand -hex 32`)
   invocado en `JwtService.__init__`: RS256 ×2 (`JWT_PRIVATE_KEY`,
   `JWT_PUBLIC_KEY`) y HS256 (`JWT_SECRET_KEY`). Fail-closed en construcción.
3. `libs/access/middleware.py` — solo docstring: el ejemplo de uso pasa de
   `secret_key="..."` hardcodeado a `os.getenv("JWT_SECRET_KEY")`.
4. `start.sh` — guard `case` que aborta (`die`, sin eco de valores) si
   `JWT_SECRET_KEY/JWT_PRIVATE_KEY/JWT_PUBLIC_KEY` siguen siendo placeholder;
   normalización de Redis URL al host que **preserva credencial y db suffix**
   (solo reescribe la parte de host).
5. `tests/security/test_d01_failclosed.py` — +11 tests (7 placeholder/
   fail-closed: rechazo de plantilla `.env.example` HS256 y RS256, mensaje sin
   eco del valor, dev secret válido aceptado, secreto ausente sigue fallando,
   entry points leen de env sin default duro, `start.sh` contiene el guard) y
   4 de normalización Redis (`credential_preserved`,
   `credentialless_still_normalizes`, `db_suffix_preserved`,
   `foreign_host_untouched`); además endurecimiento de 2 assertions de
   issuer/audience (antes `try/except Exception: pass`, ahora
   `pytest.raises(match=…)`) — **endurecimiento, ninguna assertion debilitada,
   ningún skip/xfail**.

## Atribución histórica

Los cambios de U4 son trabajo preexistente en el worktree documentado por la
sesión **`correccion_02`** (FASE 3A — placeholders JWT fail-closed:
`_reject_placeholder`, `.env.example`, `start.sh` aborta con plantilla; y el
hallazgo "start.sh perdía la credencial Redis" + tests en
`test_d01_failclosed.py`). El audit `correccion_08` los agrupó como la unidad
U4 y esta ejecución los publica. Los hunks de issuer/audience dentro de
`test_d01_failclosed.py` fueron auditados y atribuidos explícitamente a U4
(endurecimiento de la suite adversarial), **no** a U3 (cuyo commit ya está
publicado con exactamente 2 paths). Hunk por hunk revisado: sin mezcla con
U5 (`.github/*`), U6a (services/gateway/libs/frontend), U6b (docs/ADR/state) ni
U7 (journals históricos).

## Validaciones ejecutadas (resultados reales)

- **Adversarial JwtService — 14/14 OK**: rechaza `REPLACE-WITH-*`,
  ` replace-with-x ` (espacios), `CHANGE-ME`, `change-me`, `cHaNgEmE`
  (mix-case), `...`, `<my-secret>`, PEM placeholder `-----BEGIN PRIVATE
  KEY-----…`, cadena vacía, `None`; acepta `test-secret`/dev secret y verifica
  mint+verify end-to-end con issuer/audience. Ningún mensaje eco el valor.
- `pytest tests/security/test_d01_failclosed.py` → **24 passed** (HEAD: 13).
- `pytest tests/security` → **128 passed**.
- `pytest tests/` → **766 passed**.
- `ruff check .` → rc=0; `mypy --config-file mypy.ini libs/` → rc=0 (70
  files); `bandit -r apps/ libs/ -ll -c bandit.yaml` → rc=0 (severity High 0,
  Medium 0); `python -m compileall apps libs` → rc=0; `git diff --check` →
  rc=0; `docker compose -f infrastructure/docker/docker-compose.yml
  --env-file .env config` → rc=0.
- Búsqueda de secretos en el diff: **0 credenciales reales, 0 claves
  privadas, 0 tokens** (solo fixtures legítimos de test). `.env` real no leído
  ni mostrado.
- Búsqueda de contenido comercial en el diff: **0** (sin pricing/ARR/MRR/
  churn/precios/etc.).

## Protecciones preservadas

- **JWT**: `verify_aud` sin cambios; issuer/audience de U3 intactos (U4 no
  toca `report-service/src/main.py`); validación de firma intacta; sin
  workaround `verify_aud=False` nuevo (la rama pre-existente condicionada a
  "audience no configurado" no se modifica).
- **Tenant isolation / `AuthorizationContext`**: sin cambios (0 líneas).
- **Blacklist/Redis**: política sin cambios; solo wiring de URL de U4.
- **Machine auth**: `MachineJwtService` completamente separado, 0 cambios.
- **Secretos reales**: ninguno introducido; los mensajes de error nombran la
  variable y la remediación, nunca el valor.

## Estado

- **Commit U4**: creado en esta ejecución (`AUTHORIZE_COMMIT=YES`) — SHA en
  `git log`, no inventado aquí.
- **Push**: **NO realizado** (`AUTHORIZE_PUSH=NO`); `origin/main` permanece en
  `a27988b016811c792d50b6a1c5fe67390c195ec0` hasta autorización de push.
- **Framework**: intacto (`381f56c…`, 0 staged, journal sin escrituras);
  **Framework journal modificado: NO**.
- Journals históricos y los 4 journals `??` de U7 no fueron modificados
  (esta entrada es nueva, append-only).
