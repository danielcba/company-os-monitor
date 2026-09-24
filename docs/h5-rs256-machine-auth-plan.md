# H5 — RS256 Machine Auth Production Hardening

**Status**: PLAN — NO IMPLEMENTADO
**Date**: 2026-09-12
**ADR Reference**: ADR-0005 §1 (Key Rotation)
**Depends On**: H4.0 CLOSED (commit `eb6bfd2`)

---

## Problem Statement

ADR-0005 §1 mandates RS256 with `kid`-based key rotation for machine JWTs in production. The current implementation:

- Uses HS256 (dev mode) for machine JWTs
- `JwtService` has no `kid` header claim support
- No key set — uses single `public_key` for verification
- `decode()` does not perform `kid` lookup
- Machine JWTs share the same `JwtService` instance as human JWTs (same signing key)
- No key rotation capability

**Security Impact**: Production deployment cannot use HS256 (symmetric, shared secret). RS256 with key rotation is mandatory per ADR-0005.

---

## Scope

### IN SCOPE

1. **`MachineJwtService`** — New class in `libs/access/security.py`
   - Key set: dict[str, tuple[private_key, public_key]] keyed by `kid`
   - `kid` header claim in all issued tokens
   - `kid`-based lookup during verification
   - Fail-closed: unknown `kid` → reject
   - Separate from human `JwtService`

2. **Environment variables** — Key configuration
   - `MACHINE_JWT_ACTIVE_KID` — current signing key ID
   - `MACHINE_JWT_PRIVATE_KEY_<kid>` — per-key private key (PEM)
   - `MACHINE_JWT_PUBLIC_KEY_<kid>` — per-key public key (PEM)
   - `MACHINE_JWT_KEY_OVERLAP_HOURS` — overlap window (default 24h)

3. **Gateway wiring** — `main.py`
   - Load machine keys from env vars
   - Create `MachineJwtService` instance
   - Pass to `GatewayServer` separately from human `JwtService`

4. **Machine token handler** — `health.py`
   - Use `machine_jwt` for machine token issuance/verification
   - Human `jwt` stays on `self.jwt` for human auth middleware

5. **Tests** — `tests/architecture/test_h5_rs256.py`
   - Key separation: human token signed with machine key → rejected
   - `kid` in header: token has `kid` claim
   - `kid` lookup: valid `kid` → accepted; unknown `kid` → rejected
   - Key rotation: old `kid` within overlap → accepted; after overlap → rejected
   - HS256 dev mode still works when `MACHINE_JWT_ACTIVE_KID` not set

### OUT OF SCOPE

- Human JWT changes (JwtService stays as-is)
- mTLS / certificate auth (deferred)
- Key storage infrastructure (Vault, KMS) — env vars only for MVP
- ADR modifications
- Framework modifications

---

## Implementation Plan

### Phase 1: MachineJwtService (security.py)

```python
class MachineJwtService:
    """RS256 machine JWT service with kid-based key rotation (ADR-0005 §1)."""

    def __init__(
        self,
        *,
        key_set: dict[str, tuple[str, str]],  # kid -> (private_key, public_key)
        active_kid: str,
        access_expire_seconds: int = 60,
        refresh_expire_hours: int = 24,
        overlap_hours: int = 24,
    ):
        ...

    def create_token(self, *, claims: dict, kid: str | None = None) -> str:
        """Sign token with kid in header. Uses active_kid if kid not specified."""
        ...

    def decode(self, token: str) -> dict[str, Any]:
        """Verify by kid lookup. Fail-closed on unknown kid."""
        ...
```

Key behaviors:
- `create_token` always adds `"kid": self.active_kid` to JWT header
- `decode` extracts `kid` from token header → looks up public key → verifies
- If `kid` missing from token → reject (fail-closed)
- If `kid` unknown → reject (fail-closed)
- If `kid` known but expired beyond overlap window → reject

### Phase 2: Environment Loading (main.py)

```python
def _load_machine_keys() -> dict[str, tuple[str, str]]:
    """Load MACHINE_JWT_PRIVATE_KEY_<kid> + MACHINE_JWT_PUBLIC_KEY_<kid> from env."""
    active_kid = os.getenv("MACHINE_JWT_ACTIVE_KID", "")
    keys = {}
    for key, value in os.environ.items():
        if key.startswith("MACHINE_JWT_PRIVATE_KEY_"):
            kid = key[len("MACHINE_JWT_PRIVATE_KEY_"):]
            pub_key = os.getenv(f"MACHINE_JWT_PUBLIC_KEY_{kid}", "")
            if pub_key:
                keys[kid] = (value, pub_key)
    return keys, active_kid
```

If no machine keys configured → fall back to HS256 with `MACHINE_JWT_SECRET_KEY` (dev mode).

### Phase 3: Gateway Wiring (health.py + main.py)

- `GatewayServer.__init__` receives `machine_jwt: MachineJwtService`
- Machine token handler uses `self.machine_jwt` for signing/verification
- Human auth middleware stays on `self.jwt` (unchanged)

### Phase 4: Tests

New test file: `tests/architecture/test_h5_rs256.py`

| Test | What it verifies |
|------|-----------------|
| `test_key_separation` | Human token signed with machine key → rejected by human JwtService |
| `test_kid_in_header` | Issued machine token has `kid` header claim |
| `test_kid_lookup_valid` | Token with valid `kid` → decoded successfully |
| `test_kid_unknown_rejected` | Token with unknown `kid` → InvalidTokenError |
| `test_kid_missing_rejected` | Token without `kid` → InvalidTokenError |
| `test_overlap_window` | Old `kid` within overlap → accepted |
| `test_overlap_expired` | Old `kid` beyond overlap → rejected |
| `test_hs256_dev_fallback` | No machine keys → HS256 with MACHINE_JWT_SECRET_KEY |
| `test_active_kid_used` | Token issued with active_kid, not old kid |

---

## Configuration

### Environment Variables

```bash
# Production (RS256)
MACHINE_JWT_ACTIVE_KID=key-id-v1
MACHINE_JWT_PRIVATE_KEY_key-id-v1="-----BEGIN RSA PRIVATE KEY-----\n..."
MACHINE_JWT_PUBLIC_KEY_key-id-v1="-----BEGIN PUBLIC KEY-----\n..."
MACHINE_JWT_KEY_OVERLAP_HOURS=24

# Development (HS256 fallback)
MACHINE_JWT_SECRET_KEY=dev-secret-key
```

### Key Rotation Procedure

1. Generate new key pair: `kid = key-id-v2`
2. Deploy with both keys:
   - `MACHINE_JWT_ACTIVE_KID=key-id-v2`
   - `MACHINE_JWT_PRIVATE_KEY_key-id-v1=...` (old)
   - `MACHINE_JWT_PUBLIC_KEY_key-id-v1=...` (old)
   - `MACHINE_JWT_PRIVATE_KEY_key-id-v2=...` (new)
   - `MACHINE_JWT_PUBLIC_KEY_key-id-v2=...` (new)
3. New tokens signed with `key-id-v2`
4. Old tokens verified with `key-id-v1` until overlap expires (24h)
5. After overlap: remove `key-id-v1` keys

---

## Acceptance Criteria

- [ ] `MachineJwtService` issues tokens with `kid` header
- [ ] Verification uses `kid` lookup (not single key)
- [ ] Unknown `kid` → 401 (fail-closed)
- [ ] Key separation: machine and human keys are independent
- [ ] Overlap window respected (configurable)
- [ ] HS256 dev fallback works when no machine keys configured
- [ ] All existing 623 tests pass
- [ ] New tests pass
- [ ] Ruff GREEN
- [ ] MyPy no new errors
- [ ] CI GREEN

---

## Risks

| Risk | Mitigation |
|------|------------|
| Key management complexity | Env vars for MVP; document Vault/KMS for production |
| Overlap window miscalculation | Default 24h covers max refresh lifetime (24h + buffer) |
| Breaking existing machine tokens | HS256 fallback preserves dev workflow |
| Env var secret exposure | Document: use secret manager in production, not plaintext env vars |

---

*This plan is for human review. No code has been written.*

---

## H5 — ACCEPT (2026-09-12)

**Auditor**: opencode (automated)
**Commit**: `d011d28453834b3956074ffbe4d8721f95c3922f`
**CI Run**: `34721994402` — GREEN

| Gate | Status |
|------|--------|
| G1: Git verification | ✓ PASS |
| G2: Commit inspection | ✓ PASS |
| G3: Code audit (10 invariants) | ✓ PASS |
| G4: Test audit (35 tests, 16 criteria) | ✓ PASS |
| G5: Execution (658/658 full regression) | ✓ PASS |
| G6: CI (lint-and-test + docker-build) | ✓ PASS |
| G7: H4.0 non-interference | ✓ PASS |
| G8: Domain regression (telemetry/arch/security) | ✓ PASS |
| G9: Cryptographic review | ✓ PASS |
| G10: Architectural boundary | ✓ PASS |

**Veredicto**: H5 — ACCEPT. Sistema estable. Próxima fase sujeta a aprobación humana.

**Audit report**: `docs/h5-human-acceptance-audit.md`
