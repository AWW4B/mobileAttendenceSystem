"""Key material: created on first run, stored under the data dir (git-ignored).

Each service owns its private key and publishes only the public half:
  data/portal/signing_key.pem     portal private key (signs logins + grants)
  data/mec/signing_key.pem        MEC private key (signs attendance receipts)
  data/mec/master.key             MEC template encryption + transform secret
  data/shared/portal_public.pem   MEC verifies portal tokens with this
  data/shared/mec_public.pem      portal verifies MEC receipts with this
  data/shared/admin_token.txt     dev-only admin token for enrollment tooling
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .settings import Settings


def _write_secret(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    try:
        os.chmod(path, 0o600)
    except OSError:  # Windows ignores most mode bits
        pass


def _load_or_create_ed25519(priv_path: Path, pub_path: Path) -> Ed25519PrivateKey:
    if priv_path.exists():
        key = serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
        assert isinstance(key, Ed25519PrivateKey)
    else:
        key = Ed25519PrivateKey.generate()
        _write_secret(priv_path, key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    if not pub_path.exists():
        pub_path.parent.mkdir(parents=True, exist_ok=True)
        pub_path.write_bytes(key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    return key


def _load_public(pub_path: Path, hint: str) -> Ed25519PublicKey:
    if not pub_path.exists():
        raise RuntimeError(f"{pub_path} not found. {hint}")
    key = serialization.load_pem_public_key(pub_path.read_bytes())
    assert isinstance(key, Ed25519PublicKey)
    return key


def portal_signing_key(settings: Settings) -> Ed25519PrivateKey:
    return _load_or_create_ed25519(settings.portal_dir / "signing_key.pem",
                                   settings.shared_dir / "portal_public.pem")


def portal_public_key(settings: Settings) -> Ed25519PublicKey:
    return _load_public(settings.shared_dir / "portal_public.pem",
                        "Run `python -m portal.cli init` (or start the portal once) first.")


def mec_signing_key(settings: Settings) -> Ed25519PrivateKey:
    return _load_or_create_ed25519(settings.mec_dir / "signing_key.pem",
                                   settings.shared_dir / "mec_public.pem")


def mec_public_key(settings: Settings) -> Ed25519PublicKey:
    return _load_public(settings.shared_dir / "mec_public.pem",
                        "Start the MEC server once so it publishes its receipt key.")


def load_or_create_secret(path: Path, nbytes: int = 32) -> bytes:
    if path.exists():
        return path.read_bytes()
    secret = secrets.token_bytes(nbytes)
    _write_secret(path, secret)
    return secret


def load_or_create_admin_token(settings: Settings) -> str:
    path = settings.shared_dir / "admin_token.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(32)
    _write_secret(path, token.encode())
    return token
