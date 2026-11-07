# D23 — Security Closure Continuation: G3/G4 Root-Cause, G1/G2 Activation Gate, G6 Acceptance Package & G9 Merge Policy

Unidad: D23 (`/home/dcordoba/Documents/tmp/D2_23.md`).
Fecha: 2026-10-02. Estado final: **D23: CLOSED — ROOT CAUSE DETERMINED, NO MUTATIONS EXECUTED**.
Predecessoras: D22 (remediación G1–G7/G9), D21 (sequencing), D20 (PVR evaluation).

---

## 1. Dynamic baseline

Ejecutado `git fetch --prune --tags` antes de cualquier acción.

```text
BRANCH: main
HEAD_SHA: db1819697352a0c09dc63ff4901f0063be57fc8b
MAIN_REMOTE_SHA: db1819697352a0c09dc63ff4901f0063be57fc8b
LS_REMOTE_SHA: db1819697352a0c09dc63ff4901f0063be57fc8b
HEAD↔origin/main: EQUAL
origin/main↔ls-remote: EQUAL
ALIGN: YES
HEAD tagged: v0.1.1
tags: v0.1.0, v0.1.1
pushed_at: 2026-10-01T16:40:35Z (0 actividad git remota desde D22)
releases: v0.1.1, v0.1.0 (GH = 2)
```

Baseline idéntico al cierre de D22 — verificado independientemente, no heredado.

## 2. Working tree baseline

```text
PRE-EXISTING MODIFICATIONS: M docs/release-policy.md (D13), M start.sh, M stop.sh
  (git diff stat: 3 files, 15+/3− — byte-for-byte al abrir y al cerrar)
D22 (no commit, PRESERVADO): M .github/workflows/ci.yml (+16/−0), M .github/secret_scanning.yml (+12/−4)
PRE-EXISTING UNTRACKED: 30 journals históricos
UNTRACKED D22: journal/2026/2026-10-01-g1-g7-g9-security-remediation.md (total 31 al abrir)
STAGED: 0
ENV: .env presente e intacto
```

Comandos prohibidos NO ejecutados: `reset --hard`, `clean`, `restore`, `checkout --`, `stash`.
Journals D19/D20/D21/D22 intactos y no modificados.

## 3. Authorization matrix

Aplicada estrictamente:

```text
AUTHORIZE_D23=YES
G3_G4_ROOT_CAUSE_ANALYSIS=YES
G3_G4_REMEDIATION=YES            (condicionado: sólo con evidencia nueva completa)
GITHUB_SECURITY_SETTINGS_CHANGE=YES
G1_G2_ACTIVATION_ANALYSIS=YES
CI_REMOTE_VERIFICATION=NO
G6_ACCEPTANCE_PREPARATION=YES
G6_HISTORICAL_ACCEPTANCE=NO
G9_TRIAGE=YES
PR_MERGE/PR_CLOSE/PR_REBASE/FORCE_PUSH=NO
LICENSE_AUDIT/LICENSE_CHANGE=NO
PVR_ENABLE/PVR_DISABLE=NO
V012_*=NO  SPRINT_13=NO
COMMIT=NO  PUSH=NO  TAG=NO  GITHUB_RELEASE=NO
```

**Mutaciones ejecutadas en D23: 0.** Ningún PATCH G3/G4 (la condición de evidencia
nueva para retry no se activó — ver §5/§8), ningún cambio GitHub, ningún commit/push.

## 4. D22 continuity verification

Revalidación de los 8 estados críticos (FASE 2), con DIFF FROM D22:

```text
G1: CLOSED → idéntico. ci.yml conserva los 2 steps SCA
    (lines 169/178: npm audit + pip-audit==2.10.1), excepción PYSEC-2026-1325
    documentada (lines 180/186). YAML válido. DIFF: NONE → ACTION: activation gate.
G2: CLOSED → idéntico. paths-ignore = 3 (.env.example, node_modules/**, .venv*/**).
    YAML válido. DIFF: NONE → ACTION: activation gate.
G3: OPEN — BLOCKED → idéntico (disabled). DIFF: NONE → ACTION: root-cause.
G4: OPEN — BLOCKED → idéntico (disabled). DIFF: NONE → ACTION: root-cause.
G5: CLOSED → idéntico (sha_pinning_required=true; 5/5 SHA en ci.yml, 0 non-SHA).
    DIFF: NONE → ACTION: regression check.
G6: OPEN — FORMAL ACCEPTANCE REQUIRED → idéntico (required_signatures=true;
    HEAD %G?=N). DIFF: NONE → ACTION: acceptance package.
G7: CLOSED → idéntico (threat_model=remote, updated_at=2026-10-01T21:22:18Z).
    DIFF: NONE → ACTION: regression check.
G9: OPEN → 34 PRs abiertas (mismo recuento). DIFF: NONE → ACTION: inventory + policy.
```

Ninguna divergencia inesperada → sin STOP.

## 5. G3 investigation

`secret_scanning_validity_checks` acepta PATCH con 200 y permanece `disabled`
(6 intentos en D22, todos sin cambio, GET-after + cache-bust). Investigación D23
(sin mutación):

1. **Documentación oficial vigente consultada** (docs.github.com):
   - How-to "Enabling validity checks for your repository" → **"Who can use this
     feature? Validity checks for partner patterns are available for the following
     repository types: Organization-owned repositories on GitHub Team with GitHub
     Secret Protection enabled."**
   - Concept "Supported secret scanning patterns" → **"Validity and extended
     metadata checks for partner patterns are only available to users with GitHub
     Team or GitHub Enterprise who enable the feature as part of GitHub Secret
     Protection."** (nota en tabla de patterns)
   - "Evaluating alerts from secret scanning" → "Organizations using GitHub Team,
     GitHub Enterprise Cloud with a license for GitHub Secret Protection, or GitHub
     Enterprise Server with a license for GitHub Secret Protection can also enable
     validity checks for partner patterns."
2. **Endpoint**: `PATCH /repos/{owner}/{repo}` — correcto (documentado).
3. **API version**: `X-GitHub-Api-Version: 2026-03-10` (aplicado en D22, confirmado
   por `X-Github-Api-Version-Selected`).
4. **Campos soportados**: `security_and_analysis.secret_scanning_validity_checks.status`
   documentado **sólo en la variante `enterprise-cloud@latest`** de "Update a
   repository"; la variante estándar (Free/Pro/Team) de la misma página **omite el
   campo tanto del body de PATCH como del response schema GET** — mientras que la
   API en vivo de este repo sí devuelve `secret_scanning_validity_checks` en GET.
   Discrepancia documentación/entitlement que corrobora el gating por producto.
5. **Permisos**: admin sobre el repo — verificado (admin de la cuenta owner; todos
   los PATCH devolvieron 200, no 403).
6. **Requisitos de repo/org**: repo user-owned (personal), no organization-owned.
7. **Entitlement de producto**: cuenta Free; sin GitHub Team; sin licencia GitHub Secret
   Protection. **0/3 condiciones oficiales cumplidas.**
8. **Visibilidad**: público — relevante para secret scanning base (gratuito), NO
   para validity checks partner (gate distinto: org + Team + Secret Protection).
9. **Región**: sin condición regional documentada (github.com SaaS).
10. **Preview**: la nota de preview aplica a "extended metadata checks", no a la
    disponibilidad de validity checks.
11. **Comportamiento ante campos no disponibles**: no hay código de error
    documentado para "feature not entitled"; observado empíricamente: 200 + sin
    cambio. Control D22: enum inválido (`status:"bogus"`) también devuelve 200 →
    el endpoint no valida ni señala campos no aplicables → **"accepted but not
    applicable"** es consistente con la semántica observada.
12. **Headers**: `X-Github-Api-Version-Selected` confirmó versión aplicable;
    sin header de advertencia.
13. **Códigos HTTP documentados** de PATCH: 200/307/403/404/422 — 200 es el
    código esperado para un update bien formado; la doc no declara 4xx por
    falta de entitlement.

## 6. G3 root cause

```text
ROOT CAUSE: ENTITLEMENT (FEATURE AVAILABILITY — categoría prompt: entitlement de producto)
CATEGORÍA: no REPOSITORY CONFIGURATION, no PERMISSION, no REQUEST SHAPE,
  no PLATFORM BUG — disponibilidad de la feature condicionada oficialmente a
  org-owned + GitHub Team + GitHub Secret Protection; este repo cumple 0/3.
EVIDENCE:
  - docs how-to "Enabling validity checks for your repository" (Who can use: org-owned
    on Team with Secret Protection)
  - docs "Supported secret scanning patterns" (validity checks partner = Team/Enterprise
    con Secret Protection)
  - docs "Evaluating alerts from secret scanning" (mismo gate)
  - schema PATCH `secret_scanning_validity_checks` presente sólo en variante
    enterprise-cloud de la doc REST; ausente en la variante estándar
  - API vivo: GET devuelve el campo (disabled); PATCH 200 sin cambio (D22 ×6)
  - control: enum inválido también 200 → endpoint no valida/no señala
MECANISMO: request correcto y autorizado; la plataforma no aplica el cambio porque
  el entitlement no existe → "accepted but not applicable".
WHY NO LOCAL REMEDIATION EXISTS: no puede convertirse repo user-owned → org;
  no puede habilitarse Team ni Secret Protection sin adquisición/compra (acción
  comercial, explícitamente fuera de alcance); no existe toggle alternativo.
WHY RETRY IS NOT JUSTIFIED: endpoint/campo/permiso/version ya correctos y
  verificados; falta sólo el entitlement; cualquier PATCH repetido golpea el mismo
  gate → mismo no-op. La condición de evidencia nueva completa del prompt
  (NEW ROOT CAUSE + CORRECT ENDPOINT + FIELD + PERMISSION + DOCUMENTED EXPECTED
  EFFECT) NO se cumple para efecto distinto al ya observado.
WHAT EXTERNAL CONDITION IS REQUIRED: (a) transferir el repo a una organización en
  GitHub Team con GitHub Secret Protection habilitado y then habilitar vía settings
  o REST; o (b) licenciar GitHub Secret Protection para la organización. Ambas
  condiciones externas (ownership/licencia de producto), ninguna local.
```

## 7. G3 disposition

```text
G3 = OPEN — PLATFORM / ENTITLEMENT BLOCKED
PATCH RETRY D23: NOT EXECUTED (evidencia nueva determinó que no hay corrección
  local demostrable — la evidencia demostró lo contrario)
SETTING EFFECTIVELY ENABLED: no
```

## 8. G4 investigation

`secret_scanning_non_provider_patterns` — mismo protocolo:

1. How-to oficial "Enabling secret scanning for non-provider patterns" →
   **"Who can use this feature? … Scanning for non-provider patterns is available
   for the following repository types: Organization-owned repositories on GitHub
   Team with GitHub Secret Protection enabled."**
2. "Supported secret scanning patterns" → "For secret scanning to scan for
   non-provider patterns, the detection of non-provider patterns must be enabled
   for the repository or the organization" — condición habilitarse, precedida por
   el gate de disponibilidad del how-to.
3. Endpoint/field/permission/version: correctos (campo SÍ documentado en la
   variante estándar del PATCH — a diferencia de G3), admin verificado, 200 sin
   cambio (D22 ×2 + combinado), GET-after disabled.
4. Mismo control de enum inválido → 200.
5. Repo user-owned + Free + sin Secret Protection → 0/3 condiciones oficiales.

## 9. G4 root cause

```text
ROOT CAUSE: ENTITLEMENT (FEATURE AVAILABILITY) — misma clase que G3.
EVIDENCE: docs how-to "Enabling secret scanning for non-provider patterns"
  (org-owned + Team + Secret Protection); schema del campo documentado pero la
  disponibilidad de la feature excluye repos user-owned en cuenta Free; API 200
  sin cambio; control enum inválido 200.
WHY NO LOCAL REMEDIATION EXISTS: mismas razones que G3 (propiedad/licencia
  no modificables localmente; compra fuera de alcance).
WHY RETRY IS NOT JUSTIFIED: forma de request ya correcta y verificada; falta el
  entitlement; retry = mismo no-op.
WHAT EXTERNAL CONDITION IS REQUIRED: org-owned + GitHub Team + GitHub Secret
  Protection habilitado (o licencia Secret Protection), luego habilitar desde
  settings/REST para el repo.
```

## 10. G4 disposition

```text
G4 = OPEN — PLATFORM / ENTITLEMENT BLOCKED
PATCH RETRY D23: NOT EXECUTED
SETTING EFFECTIVELY ENABLED: no
```

## 11. G1 activation readiness

```text
G1 LOCAL IMPLEMENTATION = READY
  - steps presentes: "Frontend dependency audit (SCA)" (npm audit, line 173) y
    "Dependency audit (SCA)" (pip install pip-audit==2.10.1 + pip-audit
    --ignore-vuln PYSEC-2026-1325, lines 185-186)
  - política de fallo explícita en comments (lines 178-181); excepción única
    documentada (PYSEC-2026-1325, ecdsa)
  - semántica de fallo verificada en D22 en ambos sentidos (exit 1 sin ignore /
    exit 0 con política; npm exit 1 con lodash vulnerable / exit 0 real)
  - YAML válido (re-validado en D23: YAML OK; 2 steps SCA)
REMOTE ACTIVATION = NOT EXECUTED
REMOTE CI VERIFICATION = NOT EXECUTED
REASON = PUSH NOT AUTHORIZED (COMMIT=NO, PUSH=NO absolutos en D23)
```

Estado reportable: `G1 = CLOSED — LOCAL IMPLEMENTATION VERIFIED; REMOTE ACTIVATION
PENDING PUSH AUTHORIZATION`.

## 12. G2 activation readiness

```text
G2 LOCAL IMPLEMENTATION = READY
  - paths-ignore = 3: .env.example, node_modules/**, .venv*/** (re-verificado D23)
  - exclusiones conservadas justificadas: placeholders por diseño / generados
    nunca tracked
  - YAML válido; header con rationale (re-validado D23: YAML OK)
  - plataforma intacta: secret_scanning=enabled, push_protection=enabled
REMOTE ACTIVATION = NOT EXECUTED (activación efectiva del file al llegar a base
  en un push futuro)
REMOTE CI VERIFICATION = NOT EXECUTED
REASON = PUSH NOT AUTHORIZED
```

Estado reportable: `G2 = CLOSED — LOCAL IMPLEMENTATION VERIFIED; REMOTE ACTIVATION
PENDING PUSH AUTHORIZATION`.

## 13. G6 acceptance package

```text
CONTROL: commits firmados requeridos en main (required_signatures)
CURRENT CONTROL STATE: enabled=true (GET /branches/main/protection/required_signatures)
HISTORICAL EXCEPTION: HEAD db18196… no firmado (%G? = N; verify-commit falla)
AFFECTED COMMIT: db1819697352a0c09dc63ff4901f0063be57fc8b (HEAD, ancla de v0.1.1)
  y el historial previo sin firmar
WHY HISTORY REWRITE IS PROHIBITED: tags v0.1.0/v0.1.1 y releases anclan el
  historial; reescribir (rebase/filter/amend/force-push) rompe provenance e
  integridad de releases; prohibido explícitamente por la unidad (G6_HISTORICAL
  ACCEPTANCE=NO) y por práctica de release
CURRENT PROTECTION: required_signatures aplica a commits futuros; branch
  protection (1 review, contexts lint-and-test/docker-build, enforce_admins=false)
RESIDUAL RISK: historial pre-existente sin firma criptográfica — la provenance
  de SHAs históricos se apoya en transporte/GitHub UI, no en firmas
SCOPE: exclusivamente commits anteriores a la activación del control
IMPACT: attestation/auditoría de SHAs históricos no verificable criptográficamente;
  nuevos commits quedan cubiertos por el control activo
MITIGATION: control activo para futuro + no-rewrite preserva tags/releases;
  riesgo residual acotado y documentado
ACCEPTANCE REQUIRED FROM: propietario/maintainer del repo (decisión humana
  explícita; unidad futura con G6_HISTORICAL_ACCEPTANCE=YES o sign-off formal)
```

```text
G6 = OPEN — FORMAL ACCEPTANCE REQUIRED
```

No se ejecutó rebase/filter-repo/filter-branch/amend/force-push.

## 14. G9 dynamic inventory

Recalculado dinámicamente (no heredado): **34 PRs abiertas** (#19–#52).

```text
BLOCKED BY REVIEW (29): #21,#23,#24,#27–#52 — checks 2/2 SUCCESS,
  reviewDecision=REVIEW_REQUIRED, mergeStateStatus=BLOCKED, not behind
BEHIND / REBASE REQUIRED (4): #19,#20,#22,#26 — checks 2/2 SUCCESS,
  mergeStateStatus=BEHIND; todas modifican SÓLO ci.yml (SHA-pinned verificado)
BLOCKED BY CI (1): #25 — lint-and-test (3.12, 24) FAILURE, docker-build SKIPPED
SUPERSEDED: 0   DUPLICATE: 0 (pares homónimos = manifiestos distintos)
merged histórico: 19 (#1–#18, #53); cerradas sin merge: 0
reviews: las 34 con REVIEW_REQUIRED (branch protection: 1 approving review)
0 merges/cierres/rebases/force-push en D23
```

## 15. G9 future merge policy (definida, NO ejecutada)

Gates mínimos por PR (todos obligatorios):

```text
PR CHECKS GREEN
+ REQUIRED REVIEW PRESENT (≥1 approving review)
+ NOT BEHIND (rebase/update branch si BEHIND, con post-rebase CI green)
+ NO SECURITY REGRESSION (settings/audit sin cambios de seguridad)
+ NO SHA-PINNING REGRESSION (actions siguen a 40-hex auténticos)
+ NO UNRELATED FILE CHANGES (diff acotado al manifiesto declarado)
+ NO RELEASE BOUNDARY VIOLATION (CHANGELOG/README/versiones/tags intocados)
```

Clases:
- 29 BLOCKED BY REVIEW → requieren review humana; merge individual tras approve.
- 4 BEHIND (Actions, ci.yml) → rebase obligatorio (unidad con PR_REBASE=YES);
  post-rebase CI green; preservar pins SHA + preservar steps SCA G1 + re-validar
  YAML; verificar comentario de versión del pin (hallazgo: comentarios `# vX` del
  diff no coinciden con el tag real del SHA propuesto — cosmético, ver §17).
- #25 → FUTURE REMEDIATION primero (ver §16); no merge hasta CI green.

Prohibido "merge all"/lotes masivos: cada PR se evalúa individualmente contra los
gates. Unidad de ejecución futura y separada (G9 merge unit con PR_MERGE=YES).

## 16. PR #25 analysis

```text
PR: #25 "chore(deps): bump react and @types/react in /apps/web" (grouped "multi")
HEAD: b3459562bbc05e17f42d6190f0bc8ad13ab50848  BASE: main
STATE: BLOCKED / REVIEW_REQUIRED
CHECKS: lint-and-test (3.12, 24) = FAILURE; docker-build = SKIPPED
RUN: 36892881359 = failure (único run del commit; verificado en D23)
FAILURE ACTUAL (grep fresco del log): "Error: Incompatible React versions: The
  'react' and 'react-dom' packages must have the exact same version."
react: ^19.2.8 → ^19.3.0 (package.json + lockfile)
@types/react: ^19.2.17 → ^19.3.0
react-dom: NO tocado (queda ^19.2.8)
affected suites: 29 suites vitest fallan al cargar (evidencia D22, misma raíz)
CONFIRMADO (no refutado): mismatch react 19.3.0 vs react-dom 19.2.8 en apps/web
DIAGNÓSTICO: grouped update dejó react-dom fuera del bump
MINIMAL FIX (NO ejecutado, fuera de alcance D23): bump react-dom a ^19.3.0 en
  apps/web/package.json + lockfile (o regrouping en dependabot.yml)
PR #25 = FUTURE REMEDIATION
```

## 17. Actions PR analysis

4 PRs de Actions (#19, #20, #22, #26), todos BEHIND + SUCCESS + sólo `ci.yml`:

```text
PR19 setup-node:  49933ea… (old) → 820762786026740c76f36085b0efc47a31fe5020
                   verificado upstream: refs/tags/v7 / v7.0.0  ✓ tag auténtico
PR20 codecov:     ab904c4… (old) → 303a32d7a59b442fa8d48b6a1cc6825c09c847a5
                   verificado upstream: refs/tags/v7 / v7.1.1   ✓ tag auténtico
PR22 setup-python:a26af69… (old) → 5fda3b95a4ea91299a34e894583c3862153e4b97
                   verificado upstream: refs/tags/v7 / v7.0.0  ✓ tag auténtico
PR26 checkout:    11d5960… (old) → 3d3c42e5aac5ba805825da76410c181273ba90b1
                   verificado upstream: refs/tags/v7 / v7.0.1  ✓ tag auténtico
```

- G5: sha_pinning_required=true; las 4 conservan 40-hex en `uses:` → **sin
  regresión de pinning en ningún diff**.
- G1: SCA baseline disponible (steps locales en working tree; tras merge de
  cualquier PR de ci.yml se requiere rebase + revalidación conjunta).
- Hallazgo cosmético preexistente/análogo: comentarios `# v4.1.0 / v3.1.1 /
  v5.4.0 / v4.2.2` de los `+` lines no coinciden con los tags reales de los SHAs
  propuestos (v7.x) — mismo patrón que los comentarios stale de ci.yml en main
  (D22 §hallazgo). Integridad de supply-chain intacta (SHA correcto); comentario
  desactualizado a corregir en la unidad de merge (edición de comentario, no
  bloqueante).
- 0 merges en D23.

## 18. Security regression

BEFORE (FASE 2 D23) vs AFTER (cierre D23) — **sin mutaciones D23**, idénticos:

```text
code_scanning: state=configured, threat_model=remote, updated_at=2026-10-01T21:22:18Z
secret_scanning: enabled | push_protection: enabled
validity_checks: disabled | non_provider_patterns: disabled  (G3/G4, bloqueo
  determinado — sin cambio de settings)
dependabot_security_updates: enabled
dependabot vulnerability alerts: open=0, fixed=11
secret-scanning alerts: open=0 | code-scanning alerts: open=0
vulnerability-alerts endpoint: 204 (enabled)
dependency graph: SBOM 485 packages
branch protection: 1 approving review, contexts [lint-and-test (3.12,24),
  docker-build], enforce_admins=false, restrictions=null
required_signatures: enabled=true
workflow permissions: default=read, can_approve=false
actions permissions: enabled=true, allowed=all, sha_pinning_required=true (G5)
G5 pins: 5/5 SHA, 0 non-SHA
G7: threat_model=remote
PVR: enabled=false
security policy: securityPolicyUrl presente (enabled)
DIFFS: 0
INTENDED: 0 (0 mutaciones)  PRE-EXISTING: 0  UNINTENDED: 0  UNKNOWN: 0
SECURITY REGRESSIONS: NONE
```

## 19. Framework integrity

```text
FRAMEWORK HEAD (open + close): 381f56cfa48d092f85846e160d2e1fe6878f9f6f
FRAMEWORK dirty (preexistente): 9 files, 4 files changed 27+/15− (idéntico)
FRAMEWORK WRITES: 0
FRAMEWORK JOURNAL WRITES: 0
```

## 20. Commercial / secrets integrity

```text
COMMERCIAL CONTENT INTRODUCED = 0 (set FASE 13 + extendido, word-boundary,
  sobre el journal y cualquier cambio — único archivo nuevo de D23)
SECRETS INTRODUCED = 0
```

## 21. Release boundary

```text
CHANGELOG/README/VERSION: intactos (0 modificación D23)
v0.1.0 / v0.1.1 / tags: intactos (HEAD sigue en v0.1.1)
GITHUB RELEASES: 2, sin cambios
LICENSE: untouched, license=null → OPEN + NOT AUTHORIZED
v0.1.2: BLOCKED + NOT AUTHORIZED
SPRINT 13: BLOCKED + NOT AUTHORIZED
PVR: DISABLED + NOT AUTHORIZED
```

## 22. Final disposition

```text
G1: CLOSED — LOCAL IMPLEMENTATION VERIFIED (remote activation pending push)
G2: CLOSED — LOCAL IMPLEMENTATION VERIFIED (remote activation pending push)
G3: OPEN — PLATFORM / ENTITLEMENT BLOCKED
    root cause: ENTITLEMENT (org-owned + Team + Secret Protection; 0/3)
G4: OPEN — PLATFORM / ENTITLEMENT BLOCKED
    root cause: ENTITLEMENT (mismo gate de disponibilidad; 0/3)
G5: CLOSED — no change (5/5 SHA, sha_pinning_required=true)
G6: OPEN — FORMAL ACCEPTANCE REQUIRED (paquete emitido §13)
G7: CLOSED — no change (threat_model=remote)
G9: OPEN — 34 PRs, 0 merges; merge policy definida (§15), decisión pendiente

MUTATIONS D23: 0 (0 PATCH G3/G4, 0 GitHub settings, 0 commits/pushes/tags/releases,
0 PR merges/closes/rebases)
INCIDENTES D23: 0 (2 consultas GraphQL con campo inexistente devolvieron error —
  read-only, sin efecto)
SEQUENCIA POST-D23: aceptación formal G6 → autorización commit/push (activar
  G1/G2) → CI remoto → unidad de merge controlado G9 → LICENSE → v0.1.2 → Sprint 13
PVR: independiente
```
