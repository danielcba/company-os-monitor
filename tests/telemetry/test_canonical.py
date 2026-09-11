"""H4.0-B1 — Canonical Serialization Library Tests.

Covers ADR-0007 §2:
- 15 canonical_float test vectors (exact match)
- ValueError for NaN / Infinity / -Infinity
- canonical_payload: batch_id removal, key sorting, nested objects, no whitespace
- payload_hash: determinism, SHA-256 64-char hex format
- Integration with realistic telemetry payload
"""

from __future__ import annotations

import hashlib
import math

import pytest

from libs.telemetry.canonical import (
    canonical_float,
    canonical_payload,
    payload_hash,
)

SHA256_HEX_LENGTH = 64

# ─────────────────────────────────────────────────────────────────────────────
# 1. canonical_float — 15 test vectors from ADR-0007 §2
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonicalFloatVectors:
    """ADR-0007 §2 float canonicalization test vectors (exact match)."""

    @pytest.mark.parametrize(
        ("input_val", "expected"),
        [
            (45, "45"),
            (45.0, "45"),
            (45.00, "45"),
            (45.2, "45.2"),
            (0.0, "0"),
            (-0.0, "0"),
            (1e3, "1000"),
            (1.0e3, "1000"),
            (0.000001, "1e-06"),
            (1e6, "1000000"),
            (0.0001, "0.0001"),
            (1e-7, "1e-07"),
            (1e15, "1000000000000000"),
            (1e16, "1e+16"),
        ],
        ids=[
            "45_int",
            "45.0_trailing_dot_zero",
            "45.00_trailing_zeros",
            "45.2_no_trailing",
            "0.0_zero",
            "-0.0_negative_zero",
            "1e3_scientific_as_int",
            "1.0e3_scientific_explicit",
            "0.000001_scientific_small",
            "1e6_large_strip_dot",
            "0.0001_decimal_small",
            "1e-7_very_small_scientific",
            "1e15_threshold_decimal",
            "1e16_threshold_scientific",
        ],
    )
    def test_float_vector(self, input_val: float, expected: str) -> None:
        assert canonical_float(input_val) == expected


# ─────────────────────────────────────────────────────────────────────────────
# 2. canonical_float — ValueError for NaN / Infinity
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonicalFloatRejects:
    """ADR-0007 §2: NaN and Infinity must be rejected."""

    def test_nan_rejected(self) -> None:
        with pytest.raises(ValueError, match="NaN"):
            canonical_float(math.nan)

    def test_positive_infinity_rejected(self) -> None:
        with pytest.raises(ValueError, match="Infinity"):
            canonical_float(math.inf)

    def test_negative_infinity_rejected(self) -> None:
        with pytest.raises(ValueError, match="Infinity"):
            canonical_float(-math.inf)


# ─────────────────────────────────────────────────────────────────────────────
# 3. canonical_float — edge cases not in the 15 vectors
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonicalFloatEdgeCases:
    def test_negative_numbers(self) -> None:
        assert canonical_float(-45.0) == "-45"
        assert canonical_float(-45.2) == "-45.2"

    def test_very_small_positive(self) -> None:
        assert canonical_float(0.0000001) == "1e-07"

    def test_integer_repr(self) -> None:
        assert canonical_float(1) == "1"
        assert canonical_float(100) == "100"

    def test_large_integer(self) -> None:
        assert canonical_float(999999) == "999999"


# ─────────────────────────────────────────────────────────────────────────────
# 4. canonical_payload — batch_id removal
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonicalPayloadBatchIdRemoval:
    """ADR-0007 §2: batch_id is the idempotency key, excluded from hash."""

    def test_batch_id_excluded(self) -> None:
        body = {"batch_id": "abc-123", "captured_at": "2026-09-02T10:00:00Z"}
        result = canonical_payload(body)
        assert b"batch_id" not in result
        assert b"captured_at" in result

    def test_batch_id_absent_in_body(self) -> None:
        body = {"captured_at": "2026-09-02T10:00:00Z"}
        result = canonical_payload(body)
        assert b"captured_at" in result


# ─────────────────────────────────────────────────────────────────────────────
# 5. canonical_payload — key sorting
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonicalPayloadKeySorting:
    """ADR-0007 §2: keys sorted lexicographically (UTF-8 byte order)."""

    def test_top_level_sorted(self) -> None:
        body = {"z_key": 1, "a_key": 2, "m_key": 3}
        result = canonical_payload(body)
        # Keys must appear in a..z order
        pos_a = result.index(b'"a_key"')
        pos_m = result.index(b'"m_key"')
        pos_z = result.index(b'"z_key"')
        assert pos_a < pos_m < pos_z

    def test_nested_keys_sorted(self) -> None:
        body = {"data": {"z": 1, "a": 2}}
        result = canonical_payload(body)
        # Nested object keys sorted
        assert b'"a":2' in result
        assert b'"z":1' in result
        pos_a = result.index(b'"a":2')
        pos_z = result.index(b'"z":1')
        assert pos_a < pos_z


# ─────────────────────────────────────────────────────────────────────────────
# 6. canonical_payload — whitespace and encoding
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonicalPayloadEncoding:
    def test_no_whitespace(self) -> None:
        body = {"key": "value"}
        result = canonical_payload(body)
        assert b" " not in result
        assert b"\n" not in result
        assert b"\t" not in result

    def test_utf8_encoding(self) -> None:
        body = {"key": "café"}
        result = canonical_payload(body)
        assert isinstance(result, bytes)
        assert "café".encode() in result

    def test_no_trailing_newline(self) -> None:
        body = {"key": "value"}
        result = canonical_payload(body)
        assert not result.endswith(b"\n")

    def test_output_is_bytes(self) -> None:
        body = {"key": "value"}
        result = canonical_payload(body)
        assert isinstance(result, bytes)


# ─────────────────────────────────────────────────────────────────────────────
# 7. canonical_payload — float values go through canonical_float
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonicalPayloadFloatNormalization:
    def test_float_45_0_becomes_45(self) -> None:
        body = {"value": 45.0}
        result = canonical_payload(body)
        assert b"45.0" not in result
        assert b"45" in result

    def test_float_negative_zero_becomes_0(self) -> None:
        body = {"value": -0.0}
        result = canonical_payload(body)
        assert b"-0" not in result
        assert b'"value":0' in result

    def test_float_scientific_notation(self) -> None:
        body = {"value": 1e-7}
        result = canonical_payload(body)
        assert b"1e-07" in result


# ─────────────────────────────────────────────────────────────────────────────
# 8. canonical_payload — nested structure serialization
# ─────────────────────────────────────────────────────────────────────────────

class TestCanonicalPayloadNested:
    def test_array_preserves_order(self) -> None:
        body = {"items": [3, 1, 2]}
        result = canonical_payload(body)
        assert b"[3,1,2]" in result

    def test_nested_dict_in_array(self) -> None:
        body = {"items": [{"b": 1, "a": 2}]}
        result = canonical_payload(body)
        assert b'"a":2' in result
        assert b'"b":1' in result
        pos_a = result.index(b'"a":2')
        pos_b = result.index(b'"b":1')
        assert pos_a < pos_b

    def test_empty_array(self) -> None:
        body = {"items": []}
        result = canonical_payload(body)
        assert b"[]" in result

    def test_empty_dict(self) -> None:
        body = {}
        result = canonical_payload(body)
        assert result == b"{}"

    def test_null_value(self) -> None:
        body = {"value": None}
        result = canonical_payload(body)
        assert b"null" in result

    def test_boolean_values(self) -> None:
        body = {"a": True, "b": False}
        result = canonical_payload(body)
        assert b"true" in result
        assert b"false" in result


# ─────────────────────────────────────────────────────────────────────────────
# 9. payload_hash — format and determinism
# ─────────────────────────────────────────────────────────────────────────────

class TestPayloadHash:
    def test_sha256_hex_format(self) -> None:
        h = payload_hash(b"test")
        assert len(h) == SHA256_HEX_LENGTH
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_input_same_hash(self) -> None:
        data = b'{"key":"value"}'
        assert payload_hash(data) == payload_hash(data)

    def test_different_input_different_hash(self) -> None:
        assert payload_hash(b"abc") != payload_hash(b"def")


# ─────────────────────────────────────────────────────────────────────────────
# 10. Integration — full round-trip with realistic payload
# ─────────────────────────────────────────────────────────────────────────────

class TestIntegrationRoundTrip:
    """Full canonical payload → hash round-trip with realistic telemetry data."""

    REALISTIC_BODY = {
        "batch_id": "550e8400-e29b-41d4-a716-446655440000",
        "captured_at": "2026-09-02T10:00:00Z",
        "installation_id": "11111111-1111-1111-1111-111111111111",
        "instance_id": "22222222-2222-2222-2222-222222222222",
        "credential_id": "33333333-3333-3333-3333-333333333333",
        "samples": [
            {
                "sequence": 1,
                "fact_type": "cpu_utilization_percent",
                "fact_value": {"value": 45.2},
                "unit": "percent",
                "labels": {"core": "0"},
            },
            {
                "sequence": 2,
                "fact_type": "memory_usage",
                "fact_value": {
                    "free_bytes": 1073741824,
                    "total_bytes": 8589934592,
                    "used_bytes": 7516192768,
                },
                "unit": "bytes",
                "labels": {},
            },
        ],
    }

    def test_deterministic_hash(self) -> None:
        h1 = payload_hash(canonical_payload(self.REALISTIC_BODY))
        h2 = payload_hash(canonical_payload(self.REALISTIC_BODY))
        assert h1 == h2
        assert len(h1) == SHA256_HEX_LENGTH

    def test_batch_id_excluded_from_hash(self) -> None:
        body_no_batch = {k: v for k, v in self.REALISTIC_BODY.items() if k != "batch_id"}
        h_with = payload_hash(canonical_payload(self.REALISTIC_BODY))
        h_without = payload_hash(canonical_payload(body_no_batch))
        assert h_with == h_without

    def test_byte_level_determinism(self) -> None:
        b1 = canonical_payload(self.REALISTIC_BODY)
        b2 = canonical_payload(self.REALISTIC_BODY)
        assert b1 == b2
        assert isinstance(b1, bytes)

    def test_captured_at_preserved_exactly(self) -> None:
        result = canonical_payload(self.REALISTIC_BODY)
        assert b'"captured_at":"2026-09-02T10:00:00Z"' in result

    def test_payload_hash_matches_manual_sha256(self) -> None:
        canonical = canonical_payload(self.REALISTIC_BODY)
        expected = hashlib.sha256(canonical).hexdigest()
        assert payload_hash(canonical) == expected


# ─────────────────────────────────────────────────────────────────────────────
# 11. Idempotency invariant
# ─────────────────────────────────────────────────────────────────────────────

class TestIdempotencyInvariant:
    """ADR-0007 §3: same batch_id + same payload → same hash (no-op)."""

    def test_same_payload_same_hash(self) -> None:
        body = {
            "batch_id": "idem-001",
            "captured_at": "2026-09-02T10:00:00Z",
            "samples": [{"sequence": 1, "fact_type": "cpu", "fact_value": {"value": 50.0}}],
        }
        h = payload_hash(canonical_payload(body))
        assert h == payload_hash(canonical_payload(body))

    def test_different_batch_id_same_payload_same_hash(self) -> None:
        body_a = {"batch_id": "aaa", "captured_at": "2026-09-02T10:00:00Z"}
        body_b = {"batch_id": "bbb", "captured_at": "2026-09-02T10:00:00Z"}
        assert payload_hash(canonical_payload(body_a)) == payload_hash(canonical_payload(body_b))


# ─────────────────────────────────────────────────────────────────────────────
# 12. Conflict detection invariant
# ─────────────────────────────────────────────────────────────────────────────

class TestConflictDetection:
    """ADR-0007 §3: same batch_id + different payload → different hash."""

    def test_different_payload_different_hash(self) -> None:
        body_a = {"batch_id": "idem-001", "captured_at": "2026-09-02T10:00:00Z"}
        body_b = {"batch_id": "idem-001", "captured_at": "2026-09-02T10:00:01Z"}
        assert payload_hash(canonical_payload(body_a)) != payload_hash(canonical_payload(body_b))

    def test_float_difference_detected(self) -> None:
        body_a = {"batch_id": "x", "value": 45.0}
        body_b = {"batch_id": "x", "value": 45.2}
        assert payload_hash(canonical_payload(body_a)) != payload_hash(canonical_payload(body_b))


# ─────────────────────────────────────────────────────────────────────────────
# 13. INV-01 through INV-10 invariants
# ─────────────────────────────────────────────────────────────────────────────

class TestInvariants:
    """Architectural invariants (ADR-0007 §4): deterministic, no leaks."""

    INVARIANT_BODY = {
        "batch_id": "inv-001",
        "captured_at": "2026-09-02T10:00:00Z",
        "samples": [
            {"sequence": 1, "fact_type": "cpu", "fact_value": {"value": 45.0}},
            {"sequence": 2, "fact_type": "mem", "fact_value": {"value": 1024}},
        ],
    }

    def test_inv01_batch_id_excluded(self) -> None:
        """INV-01: batch_id never appears in canonical bytes."""
        canonical = canonical_payload(self.INVARIANT_BODY)
        assert b"inv-001" not in canonical

    def test_inv02_deterministic_across_calls(self) -> None:
        """INV-02: same input → identical bytes across calls."""
        b1 = canonical_payload(self.INVARIANT_BODY)
        b2 = canonical_payload(self.INVARIANT_BODY)
        assert b1 == b2

    def test_inv03_sha256_64char_hex(self) -> None:
        """INV-03: hash is 64 lowercase hex characters."""
        h = payload_hash(canonical_payload(self.INVARIANT_BODY))
        assert len(h) == SHA256_HEX_LENGTH
        assert h == h.lower()
        assert all(c in "0123456789abcdef" for c in h)

    def test_inv04_float_normalization(self) -> None:
        """INV-04: 45.0 → 45 in canonical output."""
        body = {"val": 45.0}
        canonical = canonical_payload(body)
        assert b"45.0" not in canonical
        assert b"45" in canonical

    def test_inv05_negative_zero_normalized(self) -> None:
        """INV-05: -0.0 → 0 in canonical output."""
        body = {"val": -0.0}
        canonical = canonical_payload(body)
        assert b"-0" not in canonical
        assert b'"val":0' in canonical

    def test_inv06_nan_rejected(self) -> None:
        """INV-06: NaN raises ValueError."""
        with pytest.raises(ValueError, match="NaN"):
            canonical_float(math.nan)

    def test_inv07_inf_rejected(self) -> None:
        """INV-07: Infinity raises ValueError."""
        with pytest.raises(ValueError, match="Infinity"):
            canonical_float(math.inf)

    def test_inv08_no_whitespace(self) -> None:
        """INV-08: canonical output contains no whitespace."""
        canonical = canonical_payload(self.INVARIANT_BODY)
        assert b" " not in canonical
        assert b"\n" not in canonical
        assert b"\t" not in canonical

    def test_inv09_keys_sorted(self) -> None:
        """INV-09: keys appear in sorted order."""
        body = {"z": 1, "a": 2, "m": 3}
        canonical = canonical_payload(body)
        pos_a = canonical.index(b'"a"')
        pos_m = canonical.index(b'"m"')
        pos_z = canonical.index(b'"z"')
        assert pos_a < pos_m < pos_z

    def test_inv10_captured_at_exact_string(self) -> None:
        """INV-10: captured_at ISO 8601 string preserved exactly."""
        body = {"captured_at": "2026-09-02T10:00:00Z"}
        canonical = canonical_payload(body)
        assert b'"captured_at":"2026-09-02T10:00:00Z"' in canonical
