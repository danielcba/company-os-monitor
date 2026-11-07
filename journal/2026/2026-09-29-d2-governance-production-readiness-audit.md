# D2 + Governance + Production Readiness Audit — 2026-09-29

Auditoría READ-ONLY sobre el baseline `df911a8…` (prompt `correccion_49.md`).
Sin `AUTHORIZE_COMMIT`/`AUTHORIZE_PUSH`: `CHANGES APPLIED: NO`, commit=NO,
push=NO. Esta entrada es la única escritura de la tarea y queda untracked
hasta una autorización futura.

## Baseline (FACT)

- Monitor: `HEAD = origin/main = ls-remote =
  df911a8a976a5d83617060a94cd6992701a384cc`, ahead/behind `0 0`, staged `0`,
  `git diff` = solo `start.sh`/`stop.sh` (preexistentes), untracked = los 4
  journals históricos. CI de baseline: run `36649695292` (`CI`), head
  `df911a8…`, `completed/success` (`lint-and-test (3.12, 24)` y
  `docker-build` = success).
- Framework: `HEAD = origin/main = ls-remote =
  381f56cfa48d092f85846e160d2e1fe6878f9f6f`, journal 0 writes, 7 entradas.
  Worktree Framework con 9 entries locales preexistentes (4 M + 5 ??,
  presentes también en corridas anteriores): ` M .github/workflows/ci.yml`,
  ` M adr/ADR-0002…`, ` M decisions/decisions.md`,
  ` M docs/cognitive-lexicon/ontology.md`, `?? .github/CODEOWNERS`,
  `?? .github/dependabot.yml`, `?? .github/secret-scanning.yml`,
  `?? FW-PRE-COMMIT-REVIEW-REPORT.md`, `?? SECURITY.md` — clasificados
  `PRE-EXISTING`, no tocados. **Solo `.github/workflows/ci.yml` está trackeado
  en el Framework remoto**; CODEOWNERS/dependabot/secret-scanning del
  Framework existen solo en el worktree local.

## Definición verificada de D2 (sin inferencias)

Fuente canónica: `journal/2026/2026-09-29-release-governance-decision-audit.md`
§ "D2 — Release / tag policy", corroborada en
`2026-09-29-final-production-readiness-governance-audit.md` (líneas 155, 174,
207: "política release/tag → decisión humana pendiente"). No existe ninguna
otra definición de D2 en journals, docs, tests ni configuración (los usos de
"D2" en `test_03_confidence_target_swap.py` y en `statsmodels/sklearn` son
homónimos de otro namespace, no la D2 de gobernanza).

- **Objetivo:** decidir si el producto requiere tags/releases/versionado
  documental (CHANGELOG/LICENSE) o si su ausencia es deliberada.
- **Riesgo:** snapshot de release no identificable / divergencia de versiones.
- **Alcance:** tags, releases, workflows de publicación, versiones
  pyproject/package.json, CHANGELOG, LICENSE.
- **Criterios de cierre:** decisión explícita del dueño; no es una corrección
  técnica — **no tiene tests esperados**.
- **Tipo:** `FACT` (estado) + decisión humana explícita pendiente
  (`EXTERNAL`). Documentación no contradictoria → no aplica
  `REQUIRES ARCHITECTURAL DECISION` por contradicción.

## Estado D2 medido (FACT, sobre `df911a8…`)

- `git ls-remote --tags` = 0; `git tag` local = 0; API `releases` = 0; API
  `tags` = 0; 35 heads (main + dependabot/*); sin convención previa en
  `git log`.
- Un único workflow `ci.yml`, 0 pasos de publish/upload-artifact/release
  (solo Codecov informativo: "coverage upload is NOT a release gate").
- Versionado divergente: raíz `pyproject.toml` = `0.1.0`,
  `apps/web/package.json` = `0.0.0`.
- Sin CHANGELOG, sin LICENSE (`license: null` en API), repo público, no
  archivado.
- **Clasificación D2 = `EXTERNAL` (decisión humana pendiente).** Sin cambios
  desde la auditoría previa.

## Governance actual (FACT, leído sin modificar)

- **Branch protection `main`:** status checks `strict=true`
  [`lint-and-test (3.12, 24)`, `docker-build`]; PR requerido,
  `approvals=1`; `dismiss_stale_reviews=false`,
  `require_code_owner_reviews=false`, `require_last_push_approval=false`;
  `required_signatures=true`; `enforce_admins=false`;
  `allow_force_pushes=false`; `allow_deletions=false`; rulesets=0.
- **CODEOWNERS:** existe y trackeado (`* @danielcba` + adr, workflows,
  libs/access, gateway src, user-service src); coherente con Framework (que
  solo lo tiene local, sin trackear).
- **Dependabot:** config completa (17 pip + npm + github-actions, weekly
  Monday, target main); security updates `enabled`; alertas: 1 histórica
  `auto_dismissed` (undici), **0 abiertas**.
- **Secret scanning:** `enabled`; `push_protection=enabled`;
  `non_provider_patterns=disabled`; **`validity_checks=disabled`**
  (`EXTERNAL`); 0 alerts. Config propia `.github/secret_scanning.yml`
  paths-ignore verificados contra rutas existentes.
- **Code scanning:** CodeQL NO configurado — `code-scanning API → "no
  analysis found"`; solo existe `ci.yml` (`EXTERNAL`).
- **Actions policy:** workflow con `permissions: contents: read`, actions
  pineadas a SHA, `persist-credentials: false` (decisión propia del repo).

## Production readiness (FACT)

- **Configuration:** `.env.example` con placeholders fail-closed; compose
  falla cerrado con `:?` en `POSTGRES_PASSWORD`/`REDIS_PASSWORD`;
  `start.sh` rechaza placeholders JWT (`die`). `OBSERVATION`:
  `INSIGHT_HEALTH_PORT` sigue sin declararse en `.env.example` —
  **no funcional**: `start.sh` aplica default `8101`
  (`${!port_var:-$default_port}`), es inconsistencia documental.
- **Docker/Compose:** publicaciones solo loopback
  (`127.0.0.1:8080/5433/6379`), healthchecks presentes; los 16 Dockerfiles
  declaran usuario no-root (`USER 1000:1000` / `USER nginx`).
  `OBSERVATION`: compose no declara `cap_drop`/`read_only`/`security_opt`
  (hardening opcional, no blocker). D1 + perímetro de puertos intactos.
- **Runtime (ciclo completo, no destructivo):** `start.sh` rc=0 (14/14
  healthy); `ss -ltn` → los 14 servicios + 8080/5433/6379 **solo
  `127.0.0.1`** (0 fugas `0.0.0.0`); loopback **14/14 HTTP 200**; LAN
  `192.168.100.64` **14/14 + 8080 ConnectionRefused**; smoke CORS/auth:
  preflight 200 + ACAO exacto `http://localhost:8080` + credentials,
  GET sin auth 401 + ACAO, origen denegado 403 sin ACAO, sin `ACAO: *`,
  login preflight user-service 200 + ACAO; `stop.sh` rc=0 con
  "data volumes preserved"; postgres restaurado al estado pre-boot
  (28 tablas intactas).
- **Startup/Shutdown:** cambios `PRE-EXISTING` de `start.sh`/`stop.sh`
  (redis-cli `-a`, sourcing de `.env` en stop) ejecutados sin incidencias y
  **no modificados**.

## Seguridad (FACT, sin reabrir cerrados)

JWT fail-closed, Redis con requirepass + healthcheck con contraseña, Postgres
solo loopback, CORS estricto (sin wildcard), secrets scanning+push protection
activos, D1 loopback verificado en runtime, `.env` y
`apps/web/.env.development` fuera de Git, contenido comercial ausente. Sin
evidencia nueva que reabra D1/Redis/CORS/F3/U6A/U6B/U7.

## Validaciones ejecutadas (FACT)

`git diff --check` PASS · YAML válido (el "fallo" sobre `pyproject.toml` es
TOML, falso positivo) · `docker compose config -q` OK · `ruff check .` All
checks passed · `mypy --config-file mypy.ini libs/` Success (70 files) ·
`bandit -r apps/ libs/ -ll -c bandit.yaml` rc=0 (High 0 / Medium 0; 1812
low = línea base) · `python3 -m compileall apps libs` OK ·
`pytest tests/` **799 passed** (0 skipped, 0 xfail) ·
`pytest tests/security tests/architecture` **354 passed** · vitest **29
test files passed** · runtime matrix arriba. Sin relajar tests ni config.

## Resultado y decisiones pendientes

- D1 permanece `RESOLVED` (evidencia runtime reconfirmada en este SHA).
- D2 `EXTERNAL` — decisión humana: política de tags/releases/versionado.
- Limitaciones externas (4): D2; `secret_scanning_validity_checks`
  (disabled); CodeQL (no configurado); knobs de branch protection
  (`enforce_admins=false` y flags de review). Ninguna modificable aquí.
- Sin blockers técnicos sobre `df911a8…`; baseline estable y CI verde.
- Sin commit (autorizaciones no presentes), sin settings, sin Framework, sin
  Sprint 13.
