#!/usr/bin/env python3
"""Restore-verification for a COS-Monitor backup.

The only guarantee that a backup is usable is that it can be restored. This
script decrypts a chosen backup artifact and runs a smoke restore test
(e.g. pg_restore --list for the PostgreSQL dump) to confirm integrity.

Usage:
    python3 scripts/backup/verify_restore.py \
        --backup backups/backup-XXXX --passphrase "$BACKUP_PASSPHRASE"
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.storage.backup.backup import BackupError, decrypt_artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a backup is restorable")
    parser.add_argument("--backup", required=True, help="backup directory")
    parser.add_argument("--passphrase", default=os.getenv("BACKUP_PASSPHRASE", ""))
    args = parser.parse_args()

    backup_dir = Path(args.backup)
    if not backup_dir.is_dir():
        print(f"ERROR: backup dir not found: {backup_dir}")
        return 1

    pg_enc = backup_dir / "postgres.dump.enc"
    if not pg_enc.exists():
        print("ERROR: postgres.dump.enc not found in backup")
        return 1

    tmp = backup_dir / "_verify_pg.dump"
    try:
        decrypt_artifact(pg_enc, tmp, args.passphrase)
    except BackupError as exc:
        print(f"ERROR: decrypt failed: {exc}")
        return 1

    # Smoke test: pg_restore --list (verifica que el dump es legible).
    res = subprocess.run(
        ["pg_restore", "--list", str(tmp)],
        capture_output=True, text=True, check=False,
    )
    tmp.unlink(missing_ok=True)
    if res.returncode != 0:
        print(f"ERROR: pg_restore --list failed: {res.stderr[-400:]}")
        return 1

    print(f"RESTORE VERIFIED: {pg_enc.name} es legible (pg_restore --list OK)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
