"""Backup module for Company OS Monitor (external, ADR-0002).

The Backup module is the "star" reliability module of the platform: it
protects the vital data (PostgreSQL canonical stores, Redis, and generated
artifacts) with production-grade guarantees. It is an external, non-canonical
capability (ADR-0002): it never participates in the cognitive pipeline, it
only safeguards the platform's persistent state.

Reliability principles implemented (modern best practices):

1. **3-2-1 rule** — at least 3 copies, on 2 different media, 1 off-site.
2. **Cipher at rest** — every backup artifact is encrypted (AES-256) before
   being written to disk/object storage.
3. **Point-In-Time Recovery (PITR)** — PostgreSQL WAL archiving is supported
   so the platform can restore to any point in time, not just the last full
   backup.
4. **Logical backups** — `pg_dump` output as a portable safeguard and for
   cross-cluster/version restores.
5. **Verification** — a restore test is the only guarantee that a backup is
   usable ("confianza garantizada"). Every backup cadence can trigger a
   restore verification.
6. **Integrity manifest** — SHA-256 digests are recorded for every artifact so
   tampering/corruption is detectable.
7. **Retention policy** — daily/weekly/monthly rotation to bound cost.

This module intentionally does NOT shell out to external services at import
time; it exposes the primitives and the orchestration script under
``scripts/backup/``.
"""
