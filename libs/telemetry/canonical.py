"""Canonical payload serialization for telemetry ingestion.

ADR-0007 §2: language-agnostic canonical JSON algorithm producing identical
SHA-256 across Python/Go/Rust implementations.  The gateway and agent MUST
use this exact algorithm to compute ``payload_hash``.

Public API:
    canonical_float(v)       – deterministic float → string
    canonical_payload(body)  – request body → canonical UTF-8 bytes
    payload_hash(data)       – canonical bytes → 64-char hex SHA-256
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

# ── Exceptions (ADR-0007 §2) ────────────────────────────────────────────────

class CanonicalFloatError(ValueError):
    """Raised when a float value cannot be represented in canonical JSON."""

    def __init__(self, value: float) -> None:
        if math.isnan(value):
            msg = "NaN is not a valid JSON number"
        else:
            msg = "Infinity is not a valid JSON number"
        super().__init__(msg)


# ── Float normalization (ADR-0007 §2 Option B) ──────────────────────────────

def canonical_float(v: float) -> str:
    """Canonical float serialization following JSON.stringify() semantics.

    Rules (ADR-0007 §2):
    - ``NaN`` and ``Infinity`` raise ``ValueError``.
    - ``-0.0`` is normalized to ``"0"``.
    - Integer-valued floats strip trailing ``.0``.
    - Trailing zeros after decimal point are stripped.
    - Scientific notation when ``abs(v) >= 1e15`` or ``abs(v) < 1e-6``.
    """
    if math.isnan(v):
        raise CanonicalFloatError(v)
    if math.isinf(v):
        raise CanonicalFloatError(v)

    # Normalize -0.0 → 0.0
    if v == 0.0:
        v = 0.0

    s = repr(v)

    # Strip trailing zeros after decimal point and trailing decimal point
    if "." in s and "e" not in s and "E" not in s:
        s = s.rstrip("0").rstrip(".")

    return s


# ── Recursive serializer (handles nested objects with sorted keys) ───────────

def _serialize_value(v: Any) -> str:
    """Serialize a single value to canonical JSON fragment.

    Objects: keys sorted lexicographically (UTF-8 byte order).
    Arrays:  elements serialized in order.
    Floats:  canonical_float normalization.
    Others:  json.dumps (str, int, bool, None).
    """
    if isinstance(v, float):
        return canonical_float(v)
    if isinstance(v, dict):
        inner = ",".join(
            f"{json.dumps(k)}:{_serialize_value(v[k])}"
            for k in sorted(v.keys())
        )
        return "{" + inner + "}"
    if isinstance(v, list):
        inner = ",".join(_serialize_value(item) for item in v)
        return "[" + inner + "]"
    # str, int, bool, None
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False)


# ── Canonical payload (ADR-0007 §2) ────────────────────────────────────────

def canonical_payload(request_body: dict[str, Any]) -> bytes:
    """Deterministic serialization for hashing.

    Steps (ADR-0007 §2):
    1. Remove ``batch_id`` (idempotency key).
    2. Serialize recursively with sorted keys, no whitespace.
    3. Return UTF-8 bytes with no trailing newline.
    """
    payload = {k: v for k, v in request_body.items() if k != "batch_id"}

    parts = [
        f"{json.dumps(k)}:{_serialize_value(payload[k])}"
        for k in sorted(payload.keys())
    ]
    canonical = "{" + ",".join(parts) + "}"
    return canonical.encode("utf-8")


# ── SHA-256 hash (ADR-0007 §2) ─────────────────────────────────────────────

def payload_hash(data: bytes) -> str:
    """SHA-256 of canonical bytes → 64 lowercase hex characters."""
    return hashlib.sha256(data).hexdigest()
