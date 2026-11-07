# D24 — G6 Formal Acceptance Gate & G1/G2 Remote Activation Authorization Preparation

Unidad: D24 (`/home/dcordoba/Documents/tmp/D2_24.md`).
Fecha: 2026-10-02. Estado final: **D24: CLOSED — G6 DECISION FACTUALLY CLOSED, ACCEPTANCE PENDING HUMAN AUTHORIZATION**.
Predecessoras: D23 (root-cause G3/G4), D22 (remediación), D21, D20.

---

## 1. Dynamic baseline

`git fetch --prune --tags` antes de cualquier acción.

```text
BRANCH: main
HEAD_SHA: db1819697352a0c09dc63ff4901f0063be57fc8b
MAIN_REMOTE_SHA: db1819697352a0c09dc63ff4901f0063be57fc8b
LS_REMOTE_SHA: db1819697352a0c09dc63ff4901f0063be57fc8b
HEAD↔origin/main: EQUAL
origin/main↔ls-remote: EQUAL
ALIGN: YES
HEAD tagged: v0.1.1 | tags: v0.1.0, v0.1.1
```

Verificado independientemente en D24, no reutilizado de D23.

## 2. Working tree baseline

```text
PRE-EXISTING (D13/scripts): M docs/release-policy.md, M start.sh, M stop.sh
G1/G2 (D22, sin commit, preservados): M .github/workflows/ci.yml (+16/−0),
  M .github/secret_scanning.yml (+12/−4)
UNTRACKED: 32 (30 journals históricos + D22 + D23)
STAGED: 0
ENV: .env presente e intacto
HISTORICAL JOURNALS: intactos (D19–D23 sin modificar)
```

Prohibidos NO ejecutados: `reset --hard`, `clean`, `restore`, `checkout --`, `stash`.
Sin staging, sin reordenar cambios.

## 3. Authorization matrix

```text
AUTHORIZE_D24=YES
G6_ACCEPTANCE_REVIEW=YES
G6_HISTORICAL_ACCEPTANCE=NO      ← no inferible; decisión humana explícita
G1_G2_ACTIVATION_PREPARATION=YES
COMMIT=NO  PUSH=NO  TAG=NO  GITHUB_RELEASE=NO
PR_MERGE=NO  PR_CLOSE=NO  PR_REBASE=NO  FORCE_PUSH=NO
LICENSE_*=NO  PVR_*=NO  V012_*=NO  SPRINT_13=NO
```

**Mutaciones ejecutadas en D24: 0** (sólo GETs, lecturas git, docs de verificación).

## 4. G6 evidence

```text
required_signatures (main): enabled=true
enforce_admins: false
required approving review: 1
required checks: ["lint-and-test (3.12, 24)", "docker-build"] (expected)
tag v0.1.1 -> commit db1819697352a0c09dc63ff4901f0063be57fc8b (HEAD)
release v0.1.1: published 2026-10-01T16:40:58Z, target=main
```

## 5. Historical unsigned commit evidence

```text
git verify-commit db1819697352a0c09dc63ff4901f0063be57fc8b → exit=1 (sin firma)
git log -1 --format='%G? %GK' → N (sin key) — registrado, NO modificado
```

Hecho: el commit HEAD histórico (ancla de v0.1.1) y el historial previo no están
firmados. El control `required_signatures=true` ya estaba activo — la excepción es
histórica (los commits predating enforcement o que lo preceden en la línea de
historia local, sin reescribir). No se intentó convertir el commit en firmado.

## 6. G6 risk/impact

- No es una vulnerabilidad activa: es una cuestión de **provenance histórica**
  (SHA anclado por tag/release, no por firma criptográfica).
- No se minimiza: la provenance de `db18196…` y predecesores no es verificable
  criptográficamente; depende de transporte/GitHub UI.
- Mitigación actual: control activo para commits futuros + branch protection +
  no-rewrite preserva tags/releases.
- Release impact: v0.1.1 apunta a HEAD no firmado — la integridad del release se
  sostiene en tag+release de GitHub, no en firma.

## 7. Formal acceptance decision

```text
CONTROL: commits firmados requeridos en main (required_signatures)
EVIDENCE: enabled=true (§4); verify-commit exit=1 en HEAD (§5); tag/release anclan HEAD
CURRENT STATE: control activo y efectivo para futuro
HISTORICAL EXCEPTION: HEAD db18196… y predecesores sin firma
SECURITY IMPACT: provenance histórica no criptográfica; no hay bypass del
  control para nuevos commits
RELEASE IMPACT: v0.1.1 históricamente no firmado (aceptado o no por el dueño)
TECHNICAL REMEDIATION AVAILABLE: NO — la única "remediación" sería reescribir
  historia (prohibido) o firmar retroactivamente (imposible)
HISTORY REWRITE ALLOWED: NO (rebase/filter-repo/filter-branch/amend/force-push
  prohibidos)
RESIDUAL RISK: provenance histórica basada en transporte, acotada por control
  futuro activo
ACCEPTANCE REQUIRED: decisión humana explícita del propietario/maintainer

G6 = OPEN — FORMAL ACCEPTANCE REQUIRED   (G6_HISTORICAL_ACCEPTANCE=NO)
```

## 8. Future G6 authorization boundary

Paquete listo para decisión humana futura:

```text
DECISION REQUIRED:
  Accept historical unsigned provenance of commits predating required_signatures
  enforcement.
SCOPE:
  Historical commits only.
DOES NOT AUTHORIZE:
  new unsigned commits · history rewrite · force-push · release changes ·
  PR merges · configuration changes
SINGLE AUTHORIZATION TOKEN:
  AUTHORIZE_G6_HISTORICAL_ACCEPTANCE=YES
```

Esa autorización es específica y separada; no debe quedar implícita en ninguna
otra. **No ejecutada en D24.**

## 9. G1/G2 activation readiness

Revisión completa del diff (FASE 6):

```text
G1 (ci.yml +16/−0):
  ✓ pip-audit==2.10.1 (line 185) · npm audit (line 173)
  ✓ política de fallo explícita en comments (178-181)
  ✓ excepción PYSEC-2026-1325 documentada (180/186)
  ✓ semántica de fallo verificada (D22, ambos sentidos)
  ✓ YAML válido (re-validado D24)
  ✓ 0 líneas eliminadas (jobs/steps existentes intactos)
  ✓ 0 referencias `uses:` no pinneadas en el diff
G2 (secret_scanning.yml +12/−4):
  ✓ paths-ignore = 3 exactos: .env.example, node_modules/**, .venv*/**
  ✓ rationale preservado (header con nota de remediation 2026-10-02)
  ✓ YAML válido

G1/G2 LOCAL IMPLEMENTATION VERIFIED
REMOTE ACTIVATION PENDING — PUSH NOT AUTHORIZED
```

## 10. Future commit file boundary

```text
FILES INTENDED FOR FUTURE G1/G2 COMMIT:
  .github/workflows/ci.yml
  .github/secret_scanning.yml
FILES EXCLUDED:
  docs/release-policy.md (preexistente D13)
  start.sh, stop.sh (preexistentes)
  journal/** (32 untracked — incluye D22, D23 y este D24)
  .env (nunca)
  cualquier otro cambio ajeno a G1/G2
REASON: el commit de activación sólo debe contener la remediación G1/G2;
  absorber cambios ajenos rompería la separación de unidades y la trazabilidad
```

Prohibido: `git add .`, staging, commit en D24.

## 11. G5 verification

`sha_pinning_required = true` (sin cambio) · workflows 5/5 SHA en ci.yml (0 non-SHA) ·
`allowed_actions=all`, `enabled=true`. SIN MODIFICACIÓN.

## 12. G7 verification

`threat_model = remote`, `updated_at = 2026-10-01T21:22:18Z` (sin cambio desde
D22/D23). SIN MODIFICACIÓN.

## 13. G3/G4 unchanged blocked state

```text
G3 secret_scanning_validity_checks: disabled  (entitlement — sin PATCH nuevo)
G4 secret_scanning_non_provider_patterns: disabled  (entitlement — sin PATCH nuevo)
PVR: enabled=false (sin tocar)
```

Causa raíz ya determinada en D23 (ENTITLEMENT / FEATURE AVAILABILITY, 0/3
condiciones oficiales). Sin repetir PATCH mientras no cambie la condición externa.

## 14. G9 dynamic verification

```text
PRs abiertas (recuento dinámico D24): 34 — SIN CAMBIO vs D23
Merge policy de D23 vigente: CHECKS GREEN + REQUIRED REVIEW + NOT BEHIND +
  NO SECURITY REGRESSION + NO SHA PINNING REGRESSION + NO UNRELATED FILES +
  NO RELEASE BOUNDARY VIOLATION
PR mutations en D24: 0 (0 merges, 0 closes, 0 rebases, 0 force-push)
PR #25: FUTURE REMEDIATION sin cambios
```

## 15. Framework integrity

```text
FRAMEWORK HEAD: 381f56cfa48d092f85846e160d2e1fe6878f9f6f (open, idéntico al esperado)
FRAMEWORK dirty: 9 files (preexistente, sin cambios)
FRAMEWORK WRITES: 0
FRAMEWORK JOURNAL WRITES: 0
```

## 16. Pre-existing state integrity

5 modified = 3 preexistentes byte-for-byte (15+/3−) + 2 de G1/G2 intactos ·
staged=0 · `.env` intacto · D19–D23 journals intactos · 0 `reset/clean/restore/
checkout/stash` · sin archivos preexistentes añadidos al staging.
PRE-EXISTING STATE CHANGES: 0.

## 17. Commercial/secrets integrity

Journal D24 escaneado (set FASE 13 + extendido + set de secretos): ningún material
comercial de la decisión G6, ninguna credencial/token.

```text
COMMERCIAL CONTENT INTRODUCED = 0
SECRETS INTRODUCED = 0
```

## 18. Release boundary

CHANGELOG/README/VERSION/LICENSE: 0 modificación · tags `v0.1.0`/`v0.1.1` intactos
(HEAD sigue en v0.1.1) · GitHub Releases = 2 sin cambios · `release-policy.md`
preexistente intocado · estados mantenidos:

```text
v0.1.2 = BLOCKED + NOT AUTHORIZED
SPRINT 13 = BLOCKED + NOT AUTHORIZED
LICENSE = OPEN + NOT AUTHORIZED
PVR = DISABLED + NOT AUTHORIZED
```

## 19. Final disposition

```text
G1: CLOSED — LOCAL IMPLEMENTATION VERIFIED; REMOTE ACTIVATION PENDING
G2: CLOSED — LOCAL IMPLEMENTATION VERIFIED; REMOTE ACTIVATION PENDING
G3: OPEN — PLATFORM / ENTITLEMENT BLOCKED (sin cambio)
G4: OPEN — PLATFORM / ENTITLEMENT BLOCKED (sin cambio)
G5: CLOSED (sin cambio)
G6: OPEN — FORMAL ACCEPTANCE REQUIRED
    (hecho factual cerrado; decisión humana NO ejecutada:
     G6_HISTORICAL_ACCEPTANCE=NO)
G7: CLOSED (sin cambio)
G9: OPEN — MERGE POLICY DEFINED, NO MERGES (34 PRs, sin cambio)

MUTATIONS D24: 0 · COMMITS: 0 · PUSHES: 0 · PR ACTIONS: 0
SEQUENCIA POST-D24 (cada paso, autorización propia e independiente):
  1) unidad con AUTHORIZE_G6_HISTORICAL_ACCEPTANCE=YES
  2) unidad con COMMIT=YES + PUSH=YES (activa G1/G2)
  3) CI remoto
  4) unidad de merge controlado G9
  5) LICENSE → 6) v0.1.2 readiness → 7) Sprint 13
PVR: completamente separado
```
