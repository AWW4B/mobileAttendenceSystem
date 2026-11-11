"""Device request signatures.

The Android app holds an EC P-256 key in the Android Keystore (it never
leaves the secure hardware). Every state-changing request body is signed
with SHA256withECDSA and the DER signature is sent base64-encoded in the
X-Signature header. The server verifies over the exact raw body bytes, so
the app and the server never need to agree on JSON canonicalisation.
"""
from __future__ import annotations

import base64
import binascii

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


class BadSignature(Exception):
    pass


def load_device_key(pem: str) -> ec.EllipticCurvePublicKey:
    try:
        key = serialization.load_pem_public_key(pem.encode())
    except (ValueError, TypeError) as e:
        raise BadSignature("unreadable public key") from e
    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
        raise BadSignature("device key must be EC P-256")
    return key


def verify(pem: str, body: bytes, signature_b64: str | None) -> None:
    if not signature_b64:
        raise BadSignature("missing X-Signature")
    try:
        sig = base64.b64decode(signature_b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise BadSignature("signature is not base64") from e
    try:
        load_device_key(pem).verify(sig, body, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as e:
        raise BadSignature("signature does not match") from e
