"""Template protection on the MEC.

Two layers, both keyed from the MEC master secret (data/mec/master.key):

1. Cancelable transform (revocable template)
   Each stored vector is t = s * e[perm]: a secret permutation of the
   embedding's dimensions combined with secret sign flips. This is an
   orthogonal transform, so cosine similarity is unchanged and matching
   accuracy is identical. If templates leak, bump the transform version:
   every template is re-issued under new parameters and leaked ones no
   longer match anything. The phone receives the current parameters per
   session so it can transform its query embeddings the same way.

   Limitation (state it in the report): a permutation + sign flip only
   stops naive reuse/inversion of leaked vectors. A full random orthogonal
   matrix or homomorphic matching is stronger; both are research
   extensions.

2. Encryption at rest
   AES-256-GCM, with the pseudonym and transform version as associated
   data, so a ciphertext cannot be moved to another student's row.
"""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass

import numpy as np
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class InvalidVector(ValueError):
    pass


@dataclass(frozen=True)
class Transform:
    version: int
    permutation: np.ndarray  # int64, shape (dim,)
    signs: np.ndarray        # float32 of +-1, shape (dim,)

    def apply(self, v: np.ndarray) -> np.ndarray:
        return (self.signs * v[self.permutation]).astype(np.float32)

    def invert(self, t: np.ndarray) -> np.ndarray:
        out = np.empty_like(t, dtype=np.float32)
        out[self.permutation] = t * self.signs
        return out

    def to_wire(self) -> dict:
        return {
            "version": self.version,
            "permutation": self.permutation.tolist(),
            "signs": [int(s) for s in self.signs],
            "rule": "t[i] = signs[i] * e[permutation[i]]",
        }


class TemplateVault:
    def __init__(self, master_key: bytes, dim: int):
        if len(master_key) < 32:
            raise ValueError("master key must be at least 32 bytes")
        self._master = master_key
        self.dim = dim
        self._aead = AESGCM(self._derive(b"attend/template-enc/v1"))

    def _derive(self, info: bytes) -> bytes:
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(self._master)

    def transform(self, version: int) -> Transform:
        seed = int.from_bytes(self._derive(f"attend/transform/v{version}".encode()), "big")
        rng = np.random.Generator(np.random.PCG64(seed))
        perm = rng.permutation(self.dim).astype(np.int64)
        signs = rng.choice(np.array([-1.0, 1.0], dtype=np.float32), size=self.dim)
        return Transform(version, perm, signs)

    def normalize(self, values) -> np.ndarray:
        v = np.asarray(values, dtype=np.float32).reshape(-1)
        if v.shape[0] != self.dim:
            raise InvalidVector(f"expected {self.dim} values, got {v.shape[0]}")
        if not np.all(np.isfinite(v)):
            raise InvalidVector("vector contains NaN or infinity")
        n = float(np.linalg.norm(v))
        if n < 1e-6:
            raise InvalidVector("vector norm is zero")
        return (v / n).astype(np.float32)

    def seal(self, pseudonym: str, version: int, tvec: np.ndarray) -> tuple[bytes, bytes]:
        nonce = os.urandom(12)
        ct = self._aead.encrypt(nonce, tvec.astype("<f4").tobytes(), self._aad(pseudonym, version))
        return nonce, ct

    def open(self, pseudonym: str, version: int, nonce: bytes, ct: bytes) -> np.ndarray:
        raw = self._aead.decrypt(nonce, ct, self._aad(pseudonym, version))
        return np.frombuffer(raw, dtype="<f4").astype(np.float32)

    @staticmethod
    def _aad(pseudonym: str, version: int) -> bytes:
        return f"{pseudonym}|v{version}".encode()


def vector_to_b64(v: np.ndarray) -> str:
    """Wire format shared with the app: float32 little-endian, base64."""
    return base64.b64encode(np.asarray(v, dtype="<f4").tobytes()).decode()


def vector_from_b64(s: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(s), dtype="<f4").astype(np.float32)
