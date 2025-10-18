"""Authentication and authorization helpers for the MCP Bridge."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

import httpx
from fastapi import Depends, HTTPException, Request, status

try:  # pragma: no cover - exercised when python-jose is available
    from jose import JWTError, jwt
except ImportError:  # pragma: no cover - fallback for constrained environments
    from .simple_jwt import JWTError, jwt

from ..config import AppConfig


class AuthError(HTTPException):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(status_code=status_code, detail=message)


@dataclass(frozen=True)
class AuthContext:
    subject: str
    roles: List[str]
    token_id: Optional[str] = None
    issued_at: Optional[int] = None
    expires_at: Optional[int] = None
    is_service_account: bool = False


class JWTValidator:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def validate(self, token: str) -> AuthContext:
        if self._config.environment == "development" and self._config.auth_dev_secret:
            secret = self._config.auth_dev_secret
            try:
                payload = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
            except JWTError as exc:
                raise AuthError(status.HTTP_401_UNAUTHORIZED, f"Invalid dev token: {exc}") from exc
            return self._build_context(payload)

        jwks = _get_jwks(self._config.auth_jwks_url, self._config.auth_jwks_cache_seconds)
        try:
            payload = jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                audience=self._config.auth_audience,
                issuer=self._config.auth_issuer_url,
                options={"verify_at_hash": False},
            )
        except JWTError as exc:
            raise AuthError(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc
        return self._build_context(payload)

    def _build_context(self, payload: dict) -> AuthContext:
        subject = payload.get("sub")
        if not subject:
            raise AuthError(status.HTTP_401_UNAUTHORIZED, "Token missing subject")
        roles = payload.get("roles") or payload.get("scope") or []
        if isinstance(roles, str):
            roles = roles.split()
        roles = [str(role) for role in roles]
        return AuthContext(
            subject=str(subject),
            roles=roles,
            token_id=payload.get("jti"),
            issued_at=payload.get("iat"),
            expires_at=payload.get("exp"),
            is_service_account=payload.get("client_id") is not None,
        )


_JWKS_CACHE: dict[str, tuple[float, dict]] = {}


def _get_jwks(jwks_url: Optional[str], ttl_seconds: int) -> dict:
    if not jwks_url:
        raise AuthError(status.HTTP_500_INTERNAL_SERVER_ERROR, "JWKS URL is not configured")

    cached = _JWKS_CACHE.get(jwks_url)
    now = time.time()
    if cached and now - cached[0] < max(ttl_seconds, 60):
        return cached[1]

    response = httpx.get(jwks_url, timeout=5.0)
    response.raise_for_status()
    data = response.json()
    _JWKS_CACHE[jwks_url] = (now, data)
    return data


async def auth_dependency(request: Request) -> AuthContext:
    config: AppConfig = request.app.state.config
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    validator = JWTValidator(config)
    context = validator.validate(token)
    request.state.auth = context
    return context


def require_roles(*required_roles: str) -> Callable[[AuthContext], AuthContext]:
    required = {role.lower() for role in required_roles}

    def dependency(context: AuthContext = Depends(auth_dependency)) -> AuthContext:
        if not required:
            return context
        roles = {role.lower() for role in context.roles}
        if required.isdisjoint(roles):
            raise AuthError(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return context

    return dependency
