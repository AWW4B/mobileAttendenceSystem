"""Shared test helpers. Component tests live on their feature branches;
the cross-component test (test_integration.py) lives on main."""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass

import numpy as np
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from common.settings import EMBEDDING_DIM, Settings

PASSWORD = "correct-horse-battery"


@dataclass
class Device:
    """Stands in for the phone's Android Keystore key."""
    key: ec.EllipticCurvePrivateKey
    device_id: str | None = None

    @property
    def public_pem(self) -> str:
        return self.key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

    def sign(self, payload: dict) -> tuple[bytes, str]:
        body = json.dumps(payload).encode()
        sig = self.key.sign(body, ec.ECDSA(hashes.SHA256()))
        return body, base64.b64encode(sig).decode()


def new_device() -> Device:
    return Device(ec.generate_private_key(ec.SECP256R1()))


def random_embedding(seed: int) -> np.ndarray:
    v = np.random.default_rng(seed).normal(size=EMBEDDING_DIM).astype(np.float32)
    return v / np.linalg.norm(v)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path / "data")
