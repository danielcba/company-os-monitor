# CONCURRENCY_FINDINGS_FINAL.md

## Company OS Monitor — Concurrency Findings (Final)

**Date**: 2026-08-22
**Status**: COMPLETED

---

## Summary

| Finding | Severity | Status |
|---------|----------|--------|
| Refresh token race condition | P0 | ✅ Fixed |
| Rate limiter non-atomic | P1 | ✅ Fixed |
| Context activation race condition | P1 | ✅ Fixed |
| Unbounded tenant processing | P1 | ✅ Fixed |

---

## CONC-001: Refresh Token Race Condition

**Component**: Token Blacklist
**Original Pattern**:
```
check revoked → revoke → issue token
```
**Problem**: Multiple concurrent requests could pass the "check revoked" step before any of them complete the "revoke" step, allowing token reuse.

**Fix**: Atomic consume-once using Redis `SET NX EX`:
```
SET refresh:{jti} consumed NX EX ttl
```
- First request: succeeds (key created)
- Second concurrent request: fails (key already exists)

**Tests**:
- `test_consume_refresh_token_first_use_succeeds`
- `test_consume_refresh_token_replay_detected`
- `test_consume_refresh_token_different_jti_independent`
- `test_consume_refresh_token_fail_closed_on_redis_down`

**Residual Risk**: None

---

## CONC-002: Rate Limiter Non-Atomic

**Component**: Rate Limiter
**Original Pattern**:
```python
# Sync, non-atomic
def is_allowed(self, key: str) -> bool:
    hits = self._get_hits(key)
    # ... check and update
```
**Problem**: Non-atomic operations could lead to race conditions under high concurrency.

**Fix**: Atomic Lua script:
```lua
-- remove expired, count, compare, insert, expire, return
```
**Tests**:
- `test_first_request_allowed`
- `test_blocks_after_max_requests`
- `test_resets_after_window_expires`
- `test_different_keys_are_independent`

**Residual Risk**: None

---

## CONC-003: Context Activation Race Condition

**Component**: Context Store
**Original Pattern**:
```python
# Two separate commits
INSERT context
COMMIT
DEACTIVATE old context
COMMIT
```
**Problem**: If the second commit fails, the system could end up with 0 active contexts or 2 active contexts.

**Fix**: Single transaction:
```python
async with session.begin():
    INSERT context
    DEACTIVATE old context
# Both succeed or both fail
```
**Additional**: UNIQUE partial index `idx_contexts_unique_active` on `(tenant_id, purpose) WHERE is_active = true`

**Tests**: Architecture invariant test `test_one_active_context_per_purpose_constraint`

**Residual Risk**: None

---

## CONC-004: Unbounded Tenant Processing

**Component**: Multi-tenant processing
**Original Pattern**:
```python
# Unbounded parallelism
await asyncio.gather(*[process(t) for t in tenants])
```
**Problem**: Could cause database connection exhaustion and memory issues with many tenants.

**Fix**: Bounded concurrency using `asyncio.Semaphore`:
```python
processor = BoundedTenantProcessor(max_concurrent=10)
results = await processor.process_all(tenant_ids, process_fn)
```
**Configuration**:
- `MAX_CONCURRENT_TENANTS`: Default 10
- `MAX_BATCH_SIZE`: Default 100

**Tests**:
- `test_process_all_returns_results_in_order`
- `test_concurrency_is_bounded`
- `test_batch_size_limits_task_creation`

**Residual Risk**: None
