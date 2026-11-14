"""Stateless JWT validation.

Tokens are issued by tracker-service (HS256). This service only verifies them with the
shared secret, so it never needs to call the tracker or touch the user database.
"""

from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


def require_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    secret: str = request.app.state.settings.jwt_secret
    try:
        claims = jwt.decode(
            creds.credentials,
            secret,
            algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc
    return str(claims["sub"])
