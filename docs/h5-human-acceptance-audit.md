# H5 — Auditoría Formal de Aceptación Humana

**Fecha**: 2026-09-12
**Auditor**: opencode (automated)
**Solicitante**: danielcba
**Commit**: `d011d28453834b3956074ffbe4d8721f95c3922f`
**CI Run**: `34721994402` — GREEN

---

## Veredicto: H5 — ACCEPT

Todos los 10 gates de aceptación pasan. No se requiere REJECT ni CONDICIONAL.

---

## Gate 1 — Git Verification ✓

| Check | Result |
|-------|--------|
| HEAD | `d011d28453834b3956074ffbe4d8721f95c3922f` ✓ |
| origin/main | same hash ✓ |
| Branch | `main` ✓ |
| Working tree | clean (untracked: `.opencode/`, plan doc) ✓ |

## Gate 2 — Commit Inspection ✓

| File | Status | Scope |
|------|--------|-------|
| `libs/access/security.py` | M | H5 — MachineJwtService ✓ |
| `apps/gateway/api-gateway/src/main.py` | M | H5 — env loading + wiring ✓ |
| `apps/gateway/api-gateway/src/health.py` | M | H5 — machine_jwt param ✓ |
| `apps/gateway/api-gateway/src/ingest.py` | M | H5 — machine_jwt.decode ✓ |
| `apps/gateway/api-gateway/src/service.py` | M | H5 — machine_jwt param ✓ |
| `tests/architecture/test_h5_rs256.py` | A | H5 — 35 tests ✓ |
| `tests/telemetry/test_ingest_endpoint.py` | M | H5 — mock updated ✓ |

7 files, all within H5 scope. No ADRs, framework, H4.0/B1-B4, or schema files modified.

## Gate 3 — Code Audit ✓

| Invariant | Location | Status |
|-----------|----------|--------|
| RS256 hardcoded (sign) | `security.py:306-307` | ✓ |
| RS256 hardcoded (verify) | `security.py:418` | ✓ |
| kid mandatory in header | `security.py:403-405` | ✓ |
| kid maps to trusted public key | `security.py:407-412` | ✓ |
| Unknown kid → reject | `security.py:407-410` | ✓ |
| Key rotation (active_kid signs, all keys validate) | `security.py:268-271,305,412` | ✓ |
| Token type enforcement | `security.py:427-430` | ✓ |
| Human/machine separation (independent keys) | `security.py:260-293` vs `security.py:96-220` | ✓ |
| No algorithm injection | `algorithms=["RS256"]` hardcoded | ✓ |
| Ephemeral dev fallback (2048-bit RSA) | `main.py:103` | ✓ |

## Gate 4 — Test Audit ✓

35 tests across 18 classes. All use real RSA key pairs (no mocking of crypto).

| Criterion | Covered | Tests |
|-----------|---------|-------|
| RS256 obligatory | ✓ | `TestRs256Algorithm` |
| No HS256 fallback | ✓ | `TestRs256Algorithm`, `TestNonRs256Rejection` |
| kid present | ✓ | `TestKidInHeader` |
| Active kid controls issuance | ✓ | `TestActiveKidControlsIssuance` |
| Unknown kid rejected | ✓ | `TestUnknownKid` |
| Key rotation (overlap) | ✓ | `TestRotationOverlap` |
| Retired key rejected | ✓ | `TestRetiredKeyRejection` |
| Signature failure (kid mismatch) | ✓ | `TestKidMismatch` |
| Cross-key rejection | ✓ | `TestCrossKeyRejection` |
| Human/machine separation | ✓ | `TestHumanMachineSeparation` |
| Token-type separation | ✓ | `TestTokenTypeMismatch` |
| Expired token rejected | ✓ | `TestExpiredToken` |
| Config failures | ✓ | `TestConfigurationFailures` |
| Key set immutability | ✓ | `TestKeySetImmutability` |

## Gate 5 — Execution ✓

| Suite | Result |
|-------|--------|
| `test_h5_rs256.py` | **35/35 PASS** |
| Full regression | **658/658 PASS** |

## Gate 6 — CI ✓

| Job | Status |
|-----|--------|
| lint-and-test (3.12, 24) | ✓ |
| docker-build | ✓ |

Run `34721994402` completed GREEN in 6m9s.

## Gate 7 — H4.0 Non-Interference ✓

| Protected file | Modified in H5? |
|----------------|-----------------|
| `libs/cognitive_core/canonical.py` | No ✓ |
| `libs/cognitive_core/observation_id.py` | No ✓ |
| `apps/ingestion/ingest_service.py` | No ✓ |
| `apps/publishers/publisher.py` | No ✓ |
| `infrastructure/db-migrations/h4-001-schema.sql` | No ✓ |
| `adr/ADR-0005-machine-authentication.md` | No ✓ |
| `adr/ADR-0006-agent-identity-instance-lifecycle.md` | No ✓ |
| `adr/ADR-0004-transactional-outbox-observation-publisher.md` | No ✓ |
| `adr/ADR-0007-telemetry-contract-integrity.md` | No ✓ |

## Gate 8 — Domain Regression ✓

| Domain | Tests | Result |
|--------|-------|--------|
| Telemetry (H4.0) | 153/153 | ✓ |
| Architecture (incl. H5) | 117/117 | ✓ |
| Security | 96/96 | ✓ |

## Gate 9 — Cryptographic Review ✓

- RS256 hardcoded in sign + decode — no algorithm confusion
- 2048-bit RSA in dev fallback — adequate key size
- No hardcoded keys — all from env vars or ephemeral
- No private key material in logs
- `algorithms=["RS256"]` — no injection vector
- Human JWT uses separate configurable algorithm — no cross-contamination

## Gate 10 — Architectural Boundary ✓

- `MachineJwtService` is a pure security primitive (R1 external: authenticate/authorize)
- No cognitive capability introduced (no reasoning, no pattern, no hypothesis)
- Separate from human `JwtService` — independent keys, independent config
- Framework (SOLO LECTURA) not modified
- ADRs not modified

---

## Acceptance

| Gate | Status |
|------|--------|
| G1: Git | ✓ PASS |
| G2: Commit | ✓ PASS |
| G3: Code | ✓ PASS |
| G4: Tests | ✓ PASS |
| G5: Execution | ✓ PASS |
| G6: CI | ✓ PASS |
| G7: H4.0 Non-interference | ✓ PASS |
| G8: Domain Regression | ✓ PASS |
| G9: Cryptographic | ✓ PASS |
| G10: Architectural Boundary | ✓ PASS |

**VEREDICTO: H5 — ACCEPT**

H5 RS256 Machine Auth Production Hardening está completo, auditado y aceptado.
El sistema está en estado estable. Próxima fase sujeta a aprobación humana del scope.
