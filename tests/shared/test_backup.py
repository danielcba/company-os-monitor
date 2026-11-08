"""Tests for the backup module (cipher, manifest, orchestration)."""
import json
from pathlib import Path

import pytest

from libs.storage.backup.backup import (
    BackupError,
    BackupManifest,
    decrypt_artifact,
    encrypt_artifact,
    sha256_file,
)
from libs.storage.backup.orchestrator import BackupOptions, BackupOrchestrator


def test_encrypt_decrypt_roundtrip(tmp_path: Path):
    src = tmp_path / "secret.txt"
    src.write_text("vital data", encoding="utf-8")
    enc = tmp_path / "secret.enc"
    dec = tmp_path / "secret.dec"

    encrypt_artifact(src, enc, "s3cret-passphrase")
    assert enc.exists()
    assert enc.read_bytes() != src.read_bytes()  # cifrado (no es el original)

    decrypt_artifact(enc, dec, "s3cret-passphrase")
    assert dec.read_text(encoding="utf-8") == "vital data"


def test_decrypt_wrong_passphrase_fails(tmp_path: Path):
    src = tmp_path / "a.txt"
    src.write_text("x", encoding="utf-8")
    enc = tmp_path / "a.enc"
    encrypt_artifact(src, enc, "correct-pass")
    with pytest.raises(BackupError):
        decrypt_artifact(enc, tmp_path / "a.dec", "wrong-pass")


def test_sha256_file(tmp_path: Path):
    f = tmp_path / "f.bin"
    f.write_bytes(b"hello")
    assert sha256_file(f) == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_manifest_roundtrip(tmp_path: Path):
    m = BackupManifest(backup_id="b1", created_at="2026-01-01T00:00:00+00:00", kind="full")
    m.add_artifact("pg", "/x/pg.enc", "abc123", 123)
    path = tmp_path / "manifest.json"
    m.to_file(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["backup_id"] == "b1"
    assert data["artifacts"][0]["name"] == "pg"
    assert data["artifacts"][0]["sha256"] == "abc123"


def test_orchestrator_requires_passphrase():
    with pytest.raises(BackupError):
        BackupOrchestrator(BackupOptions(passphrase=""))
