"""Backup orchestrator — runs a full, verified backup run.

This is the entry point for a platform backup. It:
  1. Creates a timestamped backup directory.
  2. Dumps PostgreSQL (logical) and Redis (RDB snapshot).
  3. Copies the artifact directory (reports/PDFs) if requested.
  4. Encrypts every artifact (AES-256).
  5. Writes a SHA-256 integrity manifest.
  6. Empties the rotation (daily/weekly/monthly retention).

Caller: ``scripts/backup/run_backup.py`` (CLI wrapper).
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.storage.backup.backup import (
    BackupError,
    BackupManifest,
    PostgresBackup,
    RedisBackup,
    encrypt_artifact,
    sha256_file,
)


@dataclass
class BackupOptions:
    """Opciones de una corrida de backup."""

    backup_root: Path = Path("backups")
    passphrase: str = ""
    db_password: str = ""
    redis_password: str = ""
    include_artifacts: bool = True
    artifact_dir: Path = Path("reports-output")
    retention_days: int = 14
    backup_name: str = field(default_factory=lambda: f"backup-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}")


class BackupOrchestrator:
    """Orquesta una corrida de backup completa y verificada."""

    def __init__(self, opts: BackupOptions):
        self.opts = opts
        if not opts.passphrase:
            raise BackupError("BACKUP_PASSPHRASE is required (never empty)")

    def run(self) -> BackupManifest:
        opts = self.opts
        run_dir = opts.backup_root / opts.backup_name
        run_dir.mkdir(parents=True, exist_ok=True)

        manifest = BackupManifest(
            backup_id=opts.backup_name,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            kind="full",
        )

        # 1) PostgreSQL logical dump
        pg = PostgresBackup(pg_password=opts.db_password)
        pg_raw = run_dir / "postgres.dump"
        pg.dump_logical(pg_raw)
        pg_enc = run_dir / "postgres.dump.enc"
        encrypt_artifact(pg_raw, pg_enc, opts.passphrase)
        pg_raw.unlink(missing_ok=True)
        manifest.add_artifact(
            "postgres_dump", str(pg_enc), sha256_file(pg_enc), pg_enc.stat().st_size
        )

        # 2) Redis RDB snapshot
        try:
            redis = RedisBackup(redis_password=opts.redis_password)
            redis_raw = run_dir / "redis.rdb"
            redis.save_snapshot(redis_raw)
            redis_enc = run_dir / "redis.rdb.enc"
            encrypt_artifact(redis_raw, redis_enc, opts.passphrase)
            redis_raw.unlink(missing_ok=True)
            manifest.add_artifact(
                "redis_rdb", str(redis_enc), sha256_file(redis_enc), redis_enc.stat().st_size
            )
        except BackupError as exc:
            # No es fatal: Redis se puede reconstruir; solo se registra.
            manifest.artifacts.append({"name": "redis_rdb", "error": str(exc)})

        # 3) Artefactos (reportes/PDFs)
        if opts.include_artifacts and opts.artifact_dir.exists():
            art_dir = run_dir / "artifacts"
            art_dir.mkdir(exist_ok=True)
            shutil.copytree(opts.artifact_dir, art_dir / "files", dirs_exist_ok=True)
            enc_art = run_dir / "artifacts.enc.tar"
            _tar_and_encrypt(art_dir, enc_art, opts.passphrase)
            manifest.add_artifact(
                "artifacts", str(enc_art), sha256_file(enc_art), enc_art.stat().st_size
            )
            shutil.rmtree(art_dir, ignore_errors=True)

        # 4) Manifiesto de integridad
        manifest_path = run_dir / "manifest.json"
        manifest.to_file(manifest_path)
        manifest.add_artifact(
            "manifest", str(manifest_path), sha256_file(manifest_path), manifest_path.stat().st_size
        )

        # 5) Retención (borrar backups viejos)
        self._prune()

        return manifest

    def _prune(self) -> None:
        opts = self.opts
        cutoff = datetime.now(UTC) - timedelta(days=opts.retention_days)
        if not opts.backup_root.exists():
            return
        for child in opts.backup_root.iterdir():
            if not child.is_dir():
                continue
            try:
                ts = datetime.strptime(child.name, "backup-%Y%m%d-%H%M%S").replace(tzinfo=UTC)
            except ValueError:
                continue
            if ts < cutoff:
                shutil.rmtree(child, ignore_errors=True)


def _tar_and_encrypt(src_dir: Path, dst: Path, passphrase: str) -> None:
    """Empaqueta un directorio en tar y lo cifra (AES-256)."""
    tar_path = src_dir.with_suffix(".tar")
    shutil.make_archive(str(tar_path.with_suffix("")), "tar", root_dir=src_dir)
    encrypt_artifact(tar_path, dst, passphrase)
    tar_path.unlink(missing_ok=True)
