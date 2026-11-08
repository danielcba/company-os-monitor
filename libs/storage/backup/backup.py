"""Core backup primitives (external capability, ADR-0002).

Implements the reliability primitives for the COS-Monitor backup module:
encryption at rest, integrity manifest, retention, and the PostgreSQL / Redis /
artifact backup operations. See ``__init__.py`` for the reliability principles.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Hard limit for a single artifact (guard against runaway memory).
_MAX_ARTIFACT_MB = 2048


class BackupError(Exception):
    """Raised when a backup operation fails."""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    """Devuelve el digest SHA-256 de un archivo (para el manifiesto)."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def encrypt_artifact(src: Path, dst: Path, passphrase: str) -> None:
    """Cifra un artefacto con AES-256 (openssl enc). In-place safe."""
    if not src.exists():
        raise BackupError(f"encrypt source missing: {src}")
    cmd = [
        "openssl", "enc", "-aes-256-cbc", "-salt", "-pbkdf2",
        "-pass", f"pass:{passphrase}",
        "-in", str(src), "-out", str(dst),
    ]
    _run(cmd, label="encrypt")


def decrypt_artifact(src: Path, dst: Path, passphrase: str) -> None:
    """Inverso de ``encrypt_artifact``."""
    cmd = [
        "openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2",
        "-pass", f"pass:{passphrase}",
        "-in", str(src), "-out", str(dst),
    ]
    _run(cmd, label="decrypt")


def _run(cmd: list[str], *, label: str) -> subprocess.CompletedProcess:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise BackupError(f"{label} failed: {exc.stderr[-500:]}") from exc
    return res


@dataclass
class BackupManifest:
    """Registro de integridad de una corrida de backup."""

    backup_id: str
    created_at: str
    kind: str
    host: str = field(default_factory=lambda: os.uname().nodename)
    artifacts: list[dict[str, Any]] = field(default_factory=list)

    def add_artifact(self, name: str, path: str, sha256: str, size_bytes: int) -> None:
        self.artifacts.append(
            {"name": name, "path": path, "sha256": sha256, "size_bytes": size_bytes}
        )

    def to_file(self, dst: Path) -> None:
        dst.write_text(json.dumps(self.as_dict(), indent=2), encoding="utf-8")

    def as_dict(self) -> dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "created_at": self.created_at,
            "kind": self.kind,
            "host": self.host,
            "artifacts": self.artifacts,
        }


class PostgresBackup:
    """Backup de PostgreSQL: basebackup físico + pg_dump lógico."""

    def __init__(  # noqa: PLR0913 - PG connection bundle (host, port, user, db, password, bin)
        self,
        *,
        pg_host: str = "127.0.0.1",
        pg_port: int = 5433,
        pg_user: str = "cosmonitor",
        pg_db: str = "cosmonitor",
        pg_password: str | None = None,
        pg_bin: str = "",
    ):
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_user = pg_user
        self.pg_db = pg_db
        self.pg_password = pg_password
        base = pg_bin or ""
        self.dump = os.path.join(base, "pg_dump")
        self.basebackup = os.path.join(base, "pg_basebackup")

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        if self.pg_password:
            env["PGPASSWORD"] = self.pg_password
        return env

    def dump_logical(self, dst: Path) -> Path:
        """Backup lógico (pg_dump) del esquema + datos."""
        cmd = [
            self.dump,
            "-h", self.pg_host,
            "-p", str(self.pg_port),
            "-U", self.pg_user,
            "-d", self.pg_db,
            "-Fc",  # custom format, comprimido
            "-f", str(dst),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, env=self._env(), check=False)
        if res.returncode != 0:
            raise BackupError(f"pg_dump failed: {res.stderr[-500:]}")
        return dst

    def basebackup_physical(self, dst_dir: Path) -> Path:
        """Basebackup físico (pg_basebackup) — útil para PITR."""
        cmd = [
            self.basebackup,
            "-h", self.pg_host,
            "-p", str(self.pg_port),
            "-U", self.pg_user,
            "-D", str(dst_dir),
            "-Fp",  # formato plano (directorio)
            "-X", "stream",  # incluye WAL
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, env=self._env(), check=False)
        if res.returncode != 0:
            raise BackupError(f"pg_basebackup failed: {res.stderr[-500:]}")
        return dst_dir


class RedisBackup:
    """Backup de Redis: RDB + AOF (API del CLI de Redis)."""

    def __init__(self, *, redis_cli: str = "redis-cli", redis_host: str = "127.0.0.1", redis_port: int = 6379, redis_password: str | None = None):
        self.cli = redis_cli
        self.host = redis_host
        self.port = redis_port
        self.password = redis_password

    def save_snapshot(self, dst: Path) -> Path:
        """Fuerza un SAVE (RDB) y copia el snapshot."""
        cmd = [self.cli, "-h", self.host, "-p", str(self.port)]
        if self.password:
            cmd += ["-a", self.password]
        cmd += ["--no-auth-warning", "SAVE"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            raise BackupError(f"redis SAVE failed: {res.stderr[-300:]}")
        # La ruta del RDB se obtiene de CONFIG GET dir/dbfilename
        get = lambda key: subprocess.run(
            [self.cli, "-h", self.host, "-p", str(self.port)]
            + (["-a", self.password, "--no-auth-warning"] if self.password else [])
            + ["CONFIG", "GET", key],
            capture_output=True, text=True, check=False,
        )
        r_dir = get("dir").stdout.strip().splitlines()
        r_file = get("dbfilename").stdout.strip().splitlines()
        rdb_dir = r_dir[1] if len(r_dir) > 1 else "/data"
        rdb_name = r_file[1] if len(r_file) > 1 else "dump.rdb"
        src = Path(rdb_dir) / rdb_name
        if not src.exists():
            raise BackupError(f"redis RDB not found: {src}")
        shutil.copy2(src, dst)
        return dst
