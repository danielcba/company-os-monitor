# TEST_COVERAGE_SUMMARY.md

## Company OS Monitor — Test Coverage Summary (Final)

**Date**: 2026-08-22
**Status**: COMPLETED

---

## Summary

| Category | Tests | Status |
|----------|-------|--------|
| Architecture Invariants | 12 | ✅ |
| Tenant Scope | 9 | ✅ |
| Token Blacklist | 12 | ✅ |
| Rate Limiter | 6 | ✅ |
| Security Headers | 6 | ✅ |
| Gateway Service | 33 | ✅ |
| Boundary Rules | 10 | ✅ |
| Confidence Evidence Scope | 9 | ✅ |
| Concurrency | 6 | ✅ |
| Capability Policy | 19 | ✅ |
| Executor | 10 | ✅ |
| Tenant Scoping | 6 | ✅ |
| Cookie Auth | 8 | ✅ |
| Structured Logging | 8 | ✅ |
| Learning Pipeline | 6 | ✅ |
| **Total** | **158** | **✅** |

---

## Architecture Invariant Tests

Tests that enforce cognitive architecture rules as executable invariants:

```python
# tests/architecture/test_cognitive_invariants.py

test_observation_never_executes_action        # P1
test_canonical_tables_have_immutability_triggers  # P1
test_one_active_context_per_purpose_constraint    # P2
test_recommendation_is_not_decision               # P6
test_each_concept_has_one_store                   # R1
test_boundary_module_exists                       # R3
test_decision_requires_confidence                 # R4
test_confidence_requires_provenance               # R5
test_confidence_is_tenant_scoped                  # R5
test_cross_tenant_requires_authority              # R6
test_raw_observation_cannot_bypass_perception     # P1
```

---

## Security Tests

### Multi-Tenant Isolation
```python
# tests/gateway/test_tenant_scope.py

test_from_token_payload_copies_identity
test_resolve_no_requested_tenant_returns_own
test_resolve_same_tenant_always_allowed
test_resolve_cross_tenant_viewer_denied
test_resolve_cross_tenant_admin_denied
test_resolve_cross_tenant_superadmin_allowed
test_validate_same_tenant_passes
test_validate_same_tenant_fails
test_effective_tenant_mutable_after_creation
```

### Token Security
```python
# tests/gateway/test_token_blacklist.py

test_is_revoked_fail_closed_on_redis_down
test_is_revoked_returns_false_when_not_blacklisted
test_is_revoked_returns_true_when_blacklisted
test_is_revoked_empty_jti_returns_false
test_is_revoked_non_critical_fail_open_on_redis_down
test_is_revoked_non_critical_returns_true_when_blacklisted
test_consume_refresh_token_first_use_succeeds
test_consume_refresh_token_replay_detected
test_consume_refresh_token_different_jti_independent
test_consume_refresh_token_fail_closed_on_redis_down
test_revoke_sets_blacklist_key
test_noop_redis_does_not_raise
```

### Confidence Evidence Scope
```python
# tests/learning/test_confidence_evidence_scope.py

test_same_content_same_id
test_different_evidence_different_id
test_reordered_evidence_same_id
test_confidence_with_scoped_evidence_passes
test_confidence_with_subset_of_scope_passes
test_confidence_with_evidence_from_another_hypothesis_fails
test_empty_evidence_passes
test_same_organization_type_different_hypothesis_no_effect
test_build_confidence_includes_evidence_ids
```

---

## Concurrency Tests

```python
# tests/shared/test_concurrency.py

test_process_all_returns_results_in_order
test_concurrency_is_bounded
test_empty_input
test_single_tenant
test_batch_size_limits_task_creation
test_exception_in_one_tenant_does_not_others
```

---

## Policy Tests

```python
# tests/gateway/test_capability_policy.py

test_all_capabilities_have_policies
test_perception_family
test_reasoning_family
test_action_family_requires_confidence
test_decision_has_execution_authority
test_observation_to_evidence_allowed
test_context_to_pattern_allowed
test_hypothesis_to_insight_allowed
test_observation_to_action_blocked
test_pattern_to_decision_blocked
test_anomaly_to_recommendation_blocked
test_recommendation_to_decision_allowed
test_confidence_required_for_propose
test_confidence_not_required_for_observation
test_viewer_cannot_propose
test_admin_can_propose
test_superadmin_can_execute
test_admin_cannot_execute
test_default_policy_store
```

---

## Execution Authorization Tests

```python
# tests/action/test_executor.py

test_observation_cannot_execute
test_hypothesis_cannot_execute
test_pattern_cannot_execute
test_anomaly_cannot_execute
test_insight_cannot_execute
test_decision_can_execute_via_authorization
test_execution_authorization_requires_execute_permission
test_admin_cannot_execute
test_superadmin_can_execute_low_risk
test_superadmin_can_execute_high_risk
```

---

## Security Headers Tests

```python
# tests/shared/test_security_headers.py

test_security_headers_added
test_nonce_generated_when_use_nonce_true
test_static_csp_when_use_nonce_false
test_custom_hsts
test_request_id_preserved
test_generate_nonce_returns_hex
```

---

## Cookie Auth Tests

```python
# tests/access/test_cookie_auth.py

test_set_refresh_cookie_has_httponly
test_set_refresh_cookie_has_secure
test_set_refresh_cookie_has_samesite_strict
test_set_refresh_cookie_has_correct_path
test_set_refresh_cookie_has_max_age
test_clear_refresh_cookie
test_get_refresh_token_from_cookie
test_get_refresh_token_from_cookie_missing
```

---

## Structured Logging Tests

```python
# tests/shared/test_structured_logging.py

test_password_is_redacted
test_refresh_token_is_redacted
test_access_token_is_redacted
test_api_key_is_redacted
test_secret_is_redacted
test_bearer_token_in_string_is_redacted
test_non_sensitive_data_preserved
test_structured_logger_has_standard_fields
```
