#!/usr/bin/env python3
"""CLI wrapper for the COS-Monitor backup module.

Usage:
    python3 scripts/backup/run_backup.py \
        --root backups \
        --passphrase "$BACKUP_PASSPHRASE" \
        --db-password "$POSTGRES_PASSWORD" \
        --redis-password "$REDIS_PASSWORD" \
        --artifacts reports-output \
        --retention-days 14

Environment variables can be used instead of flags:
    BACKUP_PASSPHRASE, POSTGRES_PASSWORD, REDIS_PASSWORD, REPORT_OUTPUT_DIR
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.storage.backup.orchestrator import BackupOptions, BackupOrchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description="COS-Monitor backup runner")
    parser.add_argument("--root", default="backups", help="backup root directory")
    parser.add_argument("--passphrase", default=os.getenv("BACKUP_PASSPHRASE", ""))
    parser.add_argument("--db-password", default=os.getenv("POSTGRES_PASSWORD", ""))
    parser.add_argument("--redis-password", default=os.getenv("REDIS_PASSWORD", ""))
    parser.add_argument("--artifacts", default=os.getenv("REPORT_OUTPUT_DIR", "reports-output"))
    parser.add_argument("--retention-days", type=int, default=14)
    args = parser.parse_args()

    opts = BackupOptions(
        backup_root=Path(args.root),
        passphrase=args.passphrase,
        db_password=args.db_password,
        redis_password=args.redis_password,
        include_artifacts=True,
        artifact_dir=Path(args.artifacts),
        retention_days=args.retention_days,
    )
    orch = BackupOrchestrator(opts)
    manifest = orch.run()
    print(f"Backup OK: {manifest.backup_id}")
    for art in manifest.artifacts:
        print(f"  - {art.get('name')}: {art.get('path', art.get('error',''))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
