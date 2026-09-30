# D1 CI Clean-Checkout Test Fix — 2026-09-29

## Baseline

- Monitor SHA real: `856067966e064b36bc99e0cc3068dc669eb3ed58`
  (parent `446dd36f6c74b99958261e33a5bc073a632ee1f4`); tras
  `git fetch --prune`: `HEAD = origin/main = ls-remote`, ahead/behind `0 0`,
  staged `0`, untracked = los 4 journals históricos, `start.sh`/`stop.sh`
  modificados (preexistentes).
- Framework: `381f56cfa48d092f85846e160d2e1fe6878f9f6f` triple-match,
  0 writes al journal del Framework (7 entradas intactas).

## Fallo CI verificado

- Run: `36646320904` (workflow `CI`), headSha
  `856067966e064b36bc99e0cc3068dc669eb3ed58`, `completed/failure`.
- Job: `lint-and-test (3.12, 24)` = failure; `docker-build` = skipped
  (dependencia del job anterior).
- Test afectado:
  `tests/architecture/test_d1_loopback_bind.py::test_browser_consumers_stay_host_local`
- Error exacto: `FileNotFoundError` sobre
  `apps/web/.env.development` (lector `_read` → `pathlib.read_text`).
- Resultado CI: **798 passed, 1 failed** en Root tests; el resto de etapas
  (Service tests, Gateway tests, Frontend, Security scan) saltadas por el
  fallo.

## Root cause

El test nuevo D1 leía `apps/web/.env.development`, un archivo con la regla
gitignore `.env.*` (`.gitignore:25`), **no versionado**, presente solo en
worktrees locales; en un checkout limpio de GitHub Actions no existe. Es un
fallo de **reproducibilidad del test**, no del cambio productivo D1: las
aserciones de bind/seguridad pasaron (14/14) y el único fallo proviene de
la dependencia sobre un artefacto local no versionado.

## Decisión

Corregir el **test**, no el workflow:

- NO modificar `.github/workflows/ci.yml`.
- NO agregar `apps/web/.env.development` al repositorio.
- NO modificar `.gitignore`.
- NO crear el archivo artificialmente en CI.
- NO ocultar ni relajar el fallo.
- Conservar la intención D1: verificar que el consumidor browser permanece
  host-local.

## Dependencia eliminada

- Eliminado el `_read("apps/web/.env.development")` y las dos aserciones
  sobre `VITE_API_URL`/`VITE_USER_SERVICE_URL` que dependían de él.
- Conservadas las aserciones sobre el artefacto **trackeado**
  `apps/web/src/api/client.ts` (fallbacks canónicos
  `http://localhost:8100/api/v1` y `http://localhost:8099/api/v1`), que es el
  consumer canónico versionado del contrato browser-local.
- Docstring actualizado para describir con exactitud qué inspecciona el test
  (solo artefactos versionados). Ninguna otra aserción D1 fue alterada.
- `apps/web/.env.development` permanece **fuera de Git** (inmutado).

## Alcance exacto

Modificados (solo 2 paths):

- `tests/architecture/test_d1_loopback_bind.py` — esta corrección
- `journal/2026/2026-09-29-d1-ci-test-clean-checkout-fix.md` — esta entrada

NO modificado (declarado): `.env`, `.env.example`,
`apps/web/.env.development`, `start.sh`, `stop.sh`, journals históricos,
`.github/workflows/ci.yml`, Framework, D2, GitHub settings, CodeQL, secret
scanning, branch protection, producción/frontend/CORS/Redis/Postgres/JWT.

## Validaciones

Ejecutadas sobre el estado corregido y anotadas en el reporte final:
`git diff --check`, suite D1, `tests/security + tests/architecture`,
suite root `pytest tests/`, `ruff check .`, `mypy libs/`, `bandit`, y un
**gate de checkout limpio** que ejecuta el test en un worktree temporal sin
`apps/web/.env.development` para demostrar que ya no se requiere.

## Registros de seguridad

- Este journal no registra secretos ni valores de `.env`.
- No se inventan SHA futuros (el SHA del commit se registra en el reporte
  final una vez creado).
- Ningún journal histórico fue alterado (append-only).
