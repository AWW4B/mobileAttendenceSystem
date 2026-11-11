from __future__ import annotations

import hmac

from fastapi import HTTPException, status


def require_admin(expected: str, provided: str | None) -> None:
    if not provided or not hmac.compare_digest(expected.encode(), provided.encode()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin token required")
