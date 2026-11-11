"""EdDSA-signed JWTs.

  access   portal -> teacher login            aud: portal, mec
  grant    portal -> one-time session grant   aud: mec      (pseudonyms only)
  receipt  mec    -> verified attendance      aud: portal   (pseudonyms only)
"""
from __future__ import annotations

import time
import uuid
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from fastapi import HTTPException, status

ALG = "EdDSA"


def issue(key: Ed25519PrivateKey, *, issuer: str, typ: str, sub: str, aud: list[str], ttl_s: int,
          extra: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": issuer, "sub": sub, "aud": aud, "typ": typ,
        "iat": now, "exp": now + ttl_s, "jti": uuid.uuid4().hex,
    }
    if extra:
        claims.update(extra)
    return jwt.encode(claims, key, algorithm=ALG), claims


def verify(key: Ed25519PublicKey, token: str, *, issuer: str, typ: str, aud: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token, key, algorithms=[ALG], audience=aud, issuer=issuer,
            options={"require": ["exp", "iat", "sub", "jti", "typ"]},
        )
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    if claims.get("typ") != typ:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong token type")
    return claims


def bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    return authorization.split(" ", 1)[1].strip()
