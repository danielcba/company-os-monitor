# D2 Release Policy — Decision Package — 2026-09-29

Paquete de decisión D2 (prompt `correccion_50.md`). READ-ONLY: sin tags, sin
releases, sin cambios de versión, sin LICENSE/CHANGELOG, sin workflows,
sin settings, sin commit (`AUTHORIZE_COMMIT=NO`). Esta entrada es la única
escritura.

## Baseline (FACT)

- Monitor: `HEAD = origin/main = ls-remote =
  df911a8a976a5d83617060a94cd6992701a384cc`, ahead/behind `0 0`, staged `0`;
  CI de baseline run `36649695292` = `completed/success`.
- Estado preexistente preservado: ` M start.sh`, ` M stop.sh`, 5 journals
  untracked (4 históricos + el de `correccion_49`), `.env` gitignored.
- Framework: `381f56cfa48d092f85846e160d2e1fe6878f9f6f` triple-match
  (ls-remote OK tras un fetch con error transitorio HTTP2), journal
  0 writes, 7 entries.
- **FACT: D2 is owner decision / external governance, not framework-defined** —
  `company-os/.github` no contiene ninguna política de releases, tags,
  versionado, CHANGELOG, LICENSE ni publicación (único match: la clave de
  schema `version: 2` de dependabot.yml).

## Definición canónica D2 (FACT)

Fuente: `journal/2026/2026-09-29-release-governance-decision-audit.md`
§ "D2 — Release / tag policy"; corroborada en
`2026-09-29-final-production-readiness-governance-audit.md` y en
`2026-09-28-production-readiness-governance-audit.md` (F8: "0 release tags →
OPEN — ARCHITECTURAL DECISION"). Homónimos descartados:
`test_03_confidence_target_swap.py` (otro namespace) y libs de terceros.

1. **Objetivo:** decidir si el producto usa tags/releases/versionado
   documental o si su ausencia es deliberada.
2. **Riesgo:** snapshot no identificable + divergencia de versiones.
3. **Alcance:** tags Git, GitHub Releases, versiones, CHANGELOG, LICENSE,
   workflow de publicación.
4. **Criterios de cierre:** decisión explícita del dueño + (si aplica)
   ejecución trazable posterior. No tiene tests esperados.
5. **Dependencia humana:** total en la elección de política.
6. **Parte técnica:** inventario/medición (este paquete) + el change set de
   la opción elegida. **Parte governance:** la elección misma.

## Estado medido (FACT, sobre `df911a8…`)

### Tags
- `git tag` = 0; `git ls-remote --tags origin` = 0; API `tags` = 0.
- `git describe --tags` → `fatal: No names found`.
- Sin anotados ni lightweight. Sin relación tag→commit posible.

### GitHub Releases
- API `releases` = 0 (incluye drafts con la auth actual); 0 prereleases.
- Ninguna release asociada a `df911a8…` (el SHA existe como commit:
  "test: remove local env dependency from d1 browser bind check", 2026-09-29).

### Versionado (por componente)
- **`0.1.0` en los 18 pyprojects**: raíz + gateway + 13 services + 3 agents
  (linux/windows/vmware) — backend unificado.
- **`0.0.0` en `apps/web/package.json`** — placeholder del scaffolding Vite.
- Sin versión de plataforma única declarada; sin versionado Docker
  (sin labels `image.version`); sin versión declarada en docs.
- `INTERPRETATION`: la divergencia `0.1.0` vs `0.0.0` es separación
  intencional de ecosistemas (Python editable vs placeholder de frontend),
  no incoherencia funcional — pero no está documentada como tal.

### CHANGELOG
- Sin CHANGELOG de producto. Existen solo
  `docs/remediation/CHANGELOG_PHASE14.md` y `CHANGELOG_PHASE20.md`
  (logs de fases de remediación, alcance distinto).
- Convención de commits: **Conventional Commits de facto** — 55/60 commits
  recientes `type: descripción` (security/fix/docs/test/chore).
- 73 journals en `journal/2026/`; commits que referencian journals
  (`docs(journal): …`) → trazabilidad commit→journal existe.

### LICENSE
- Sin LICENSE/COPYING/NOTICE en el repo (0 hits, excl. node_modules).
- Sin campo `license` en pyproject/package.json; API GitHub
  `license=null`, `spdx=null`.
- `README.md` § License: "Refer to the repository files. See `LICENSE` when
  present." → referencia condicional a un archivo inexistente.
- Sin headers SPDX/copyright en código propio (solo terceros en
  node_modules).

### Release automation
- Único workflow `ci.yml` (jobs `lint-and-test`, `docker-build`):
  0 pasos de tag/release/publish/upload-artifact/registry push.
  `docker build` solo valida la imagen (sin `docker push`).
- Comentario Codecov informativo ("NOT a release gate").
- Sin scripts de release (`scripts/` solo `qa_seed.py`); sin docs de
  proceso de release manual.
- **Ausencia clasificada:** no documentada ni deliberada (nunca registrada
  como decisión) → por eso D2 está abierta.

### Snapshot
- 160 commits en la línea de HEAD; 36 heads remotos (main + dependabot/*,
  rama nueva `dependabot/npm_and_yarn/apps/web/undici-8.11.2` visible tras
  fetch — sin tocar).

## Opciones de decisión (matriz neutral, sin elegir)

### OPCIÓN A — Tagged Release
- Contenido: tag semántico (p. ej. `v0.1.0`) apuntando a `df911a8…` o a un
  SHA futuro + GitHub Release con notas + política mínima de versionado.
- Ventajas: identificación estable fuera de Git, punto de rollback público,
  convención esperada por herramientas/ecosistema, separación clara entre
  "commit" y "release".
- Costes: cada release exige bump de versión + notas + tag + release
  (proceso manual o workflow futuro); mantener 18 pyprojects + 1 package.json
  sincronizados (o aceptar versión única de producto).
- Riesgos: tag mal colocado (apunta a commit no verde), deriva de versiones
  si no se sincronizan componentes, presión para automatizar después.
- Complejidad operativa: baja-alta según si se automatiza.
- Impacto CI/CD: ninguno obligatorio (CI actual no valida tags); opcional:
  gate adicional en releases.
- Trazabilidad: alta (snapshot→tag→release→SHA).
- Impacto documental: requiere política escrita + notas de release.
- Compatibilidad con el estado actual: total (aditivo).
- Cambios necesarios: elegir número de versión; actualizar 18 pyprojects +
  `apps/web/package.json` (¿¿unificar a 0.1.0 o dejar frontend separado?);
  crear tag anotado en `df911a8…` o SHA posterior verde; crear GitHub
  Release; documentar política mínima (cuándo bump, formato); opcional
  workflow de release.

### OPCIÓN B — Untagged Snapshot
- Contenido: mantener el baseline solo por SHA; sin tags ni releases;
  documentar explícitamente que la ausencia es deliberada (entrada de journal
  + sección README); trazabilidad vía SHA + journal.
- Ventajas: cero mantenimiento continuo; coherente con el estado actual;
  sin presión de sincronización de versiones.
- Costes: sin identificación estable fuera de Git (referencia por SHA de 40
  caracteres); herramientas/ecosistema esperan tags en releases públicas.
- Riesgos: "df911a8…" difícil de citar/rollback para usuarios externos;
  si el repo se publica como producto, ausencia de LICENSE y tags golpea
  adopción; la decisión puede reabrirse bajo presión.
- Complejidad operativa: mínima.
- Impacto CI/CD: ninguno.
- Trazabilidad: media (SHA+journal suficientes internamente).
- Impacto documental: una decisión registrada (README/journal).
- Compatibilidad: total (es el estado actual + documentación).
- Cambios necesarios: registrar la decisión deliberada (journal/README);
  opcionalmente dejar de lado versiones placeholder sin cambiarlas.

### OPCIÓN C — Versionado independiente por componente
- Contenido: backend (`0.1.0`, 18 pyprojects sincronizados entre sí) y
  frontend (`0.0.0`/semver propio) con releases desacoplados; tags por
  componente (p. ej. `web-v0.1.0`, `api-v0.1.0`).
- Ventajas: refleja ecosistemas y ciclos de despliegue distintos (frontend
  build-estático vs backend Python); permite publicar uno sin el otro.
- Costes: 2 cadenas de release; matriz de compatibilidad entre componentes;
  más documentación.
- Riesgos: complejidad desproporcionada para un producto mono-repo aún en
  `0.x` sin consumidores externos identificados; confusión de "qué versión
  es la del producto".
- Complejidad operativa: la mayor de las tres.
- Impacto CI/CD: probablemente requiere workflow por componente.
- Trazabilidad: alta por componente, ambigua a nivel de producto.
- Compatibilidad: requiere reemplazar el placeholder `0.0.0` y definir
  políticas por tag namespace.
- Cambios necesarios: definir unidad de release; elegir versiones iniciales
  por componente; tags namespaced; política de compatibilidad;
  opcionalmente workflows separados.

## Decision record (borrador — sin completar)

```text
D2 DECISION

Current state:
0 Git tags (local y remoto); 0 GitHub Releases (0 drafts, 0 prereleases);
ninguna release asociada a df911a8a976a5d83617060a94cd6992701a384cc.
Versionado: 18 pyprojects = 0.1.0 (backend unificado); apps/web =
0.0.0 (placeholder Vite). Sin CHANGELOG de producto (solo logs de
remediación en docs/remediation/). Sin LICENSE (README referencia
condicional a "LICENSE when present"; API GitHub license=null).
Sin release automation (ci.yml solo lint/test/build; docker build sin push;
sin scripts ni docs de release). Convención de commits Conventional de
 facto (55/60). 73 journals como traza documental. Framework sin política
D2 formal.

Decision owner:
<OWNER / HUMAN DECISION REQUIRED>

Options:
A) Tagged Release (tag semántico + GitHub Release + política mínima de
   versionado; unifica o sincroniza versiones de componentes)
B) Untagged Snapshot (baseline solo por SHA; ausencia de tags/releases
   documentada como deliberada; trazabilidad SHA + journal)
C) Versionado independiente por componente (backend y frontend con
   releases y tags desacoplados)

Selected option:
[PENDING OWNER DECISION]

Rationale:
[PENDING OWNER DECISION]

Implementation required:
A) elegir versión; bump 18 pyprojects + apps/web/package.json (decidir
   unificación); tag apuntando a SHA verde; GitHub Release con notas;
   política escrita mínima; opcional workflow de release.
B) registrar decisión deliberada (journal/README); ningún cambio técnico.
C) definir unidad de release por componente; tags namespaced; resolver
   placeholder 0.0.0; política de compatibilidad; workflows separados
   opcionales.

Release baseline:
df911a8a976a5d83617060a94cd6992701a384cc
```

## Relación con el release baseline (FACT)

`df911a8…` es un **snapshot estable**: triple-match, CI verde
(`36649695292`), 799+354+29 tests verdes, runtime verificado. Puede seguir
funcionando como referencia mientras D2 esté pendiente. **No constituye una
"released version"**: sin tag, sin GitHub Release, sin decisión de release.
Estabilidad técnica ≠ versión publicada.

## Decisión pendiente

D2 permanece `PENDING OWNER DECISION`. No se ejecuta ninguna opción en esta
tarea. Sin blockers técnicos nuevos.
