from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings


def _extract_token(authorization: str | None, api_key: str | None) -> str | None:
    if api_key:
        return api_key.strip()
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return authorization.strip() or None


def require_api_key(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    settings = get_settings()
    if not settings.api_key:
        return

    token = _extract_token(authorization, x_api_key)
    if token != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

