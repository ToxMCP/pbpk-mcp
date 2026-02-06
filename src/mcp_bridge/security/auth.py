"""Authentication and authorization helpers for the MCP Bridge."""

from __future__ import annotations

import threading
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


_JWKS_CACHE: dict[str, tuple[float, dict]] = {}
_TOKEN_REPLAY_CACHE: dict[str, float] = {}
_TOKEN_CACHE_LOCK = threading.Lock()

_RATE_LIMIT_CACHE: dict[str, tuple[float, int]] = {}
_RATE_LIMIT_LOCK = threading.Lock()

class JWTValidator:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._clock_skew = float(getattr(config, "auth_clock_skew_seconds", 0.0))

    def validate(self, token: str) -> AuthContext:
        if (
            self._config.environment.lower() in {"development", "local"}
            and self._config.auth_dev_secret
        ):
            secret = self._config.auth_dev_secret
            try:
                payload = jwt.decode(
                    token,
                    secret,
                    algorithms=["HS256"],
                    options={"verify_aud": False},
                )
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
        now = time.time()
        exp = payload.get("exp")
        if exp is None:
            raise AuthError(status.HTTP_401_UNAUTHORIZED, "Token missing expiry")
        if float(exp) + self._clock_skew < now:
            raise AuthError(status.HTTP_401_UNAUTHORIZED, "Token expired")
        nbf = payload.get("nbf")
        if nbf is not None and float(nbf) - self._clock_skew > now:
            raise AuthError(status.HTTP_401_UNAUTHORIZED, "Token not valid yet")
        iat = payload.get("iat")
        if iat is not None and float(iat) - self._clock_skew > now:
            raise AuthError(status.HTTP_401_UNAUTHORIZED, "Token issued in the future")
        subject = payload.get("sub")
        if not subject:
            raise AuthError(status.HTTP_401_UNAUTHORIZED, "Token missing subject")
        roles = payload.get("roles") or payload.get("scope") or []
        if isinstance(roles, str):
            roles = roles.split()
        roles = [str(role) for role in roles]
        context = AuthContext(
            subject=str(subject),
            roles=roles,
            token_id=payload.get("jti"),
            issued_at=payload.get("iat"),
            expires_at=payload.get("exp"),
            is_service_account=payload.get("client_id") is not None,
        )
        _register_token(payload, self._config)
        return context


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


def _register_token(payload: dict, config: AppConfig) -> None:
    jti = payload.get("jti")
    if not jti:
        return
    now = time.time()
    expiry = float(payload.get("exp", now)) + float(getattr(config, "auth_replay_window_seconds", 0.0))
    with _TOKEN_CACHE_LOCK:
        _purge_token_cache(now)
        if jti in _TOKEN_REPLAY_CACHE and _TOKEN_REPLAY_CACHE[jti] > now:
            raise AuthError(status.HTTP_401_UNAUTHORIZED, "Token replay detected")
        _TOKEN_REPLAY_CACHE[jti] = expiry


def _purge_token_cache(now: float) -> None:
    expired = [identifier for identifier, expiry in _TOKEN_REPLAY_CACHE.items() if expiry <= now]
    for identifier in expired:
        _TOKEN_REPLAY_CACHE.pop(identifier, None)


def _enforce_rate_limit(identifier: str, config: AppConfig) -> None:
    limit = getattr(config, "auth_rate_limit_per_minute", 0)
    if limit <= 0:
        return
    window = 60.0
    now = time.time()
    with _RATE_LIMIT_LOCK:
        count, reset = _RATE_LIMIT_CACHE.get(identifier, (0, now + window))
        if now > reset:
            _RATE_LIMIT_CACHE[identifier] = (1, now + window)
            return
        if count >= limit:
            raise AuthError(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded")
        _RATE_LIMIT_CACHE[identifier] = (count + 1, reset)


def _rate_limit_identity(request: Request) -> str:
    client = request.client
    if client and client.host:
        return client.host
    return "unknown"


async def auth_dependency(request: Request) -> AuthContext:
    config: AppConfig = request.app.state.config
    _enforce_rate_limit(_rate_limit_identity(request), config)
    
    # Case 1: No auth backend configured at all
    if not config.auth_dev_secret and not config.auth_jwks_url:
        if config.auth_allow_anonymous:
            context = AuthContext(
                subject="anonymous",
                roles=["admin", "operator", "viewer"],
                is_service_account=True,
            )
            request.state.auth = context
            return context
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Authentication configuration is missing")

    authorization = request.headers.get("Authorization")
    
    # Case 2: Auth backend exists, but no token provided
    if not authorization or not authorization.startswith("Bearer "):
        if config.auth_allow_anonymous:
            context = AuthContext(
                subject="anonymous",
                roles=["admin", "operator", "viewer"],
                is_service_account=True,
            )
            request.state.auth = context
            return context
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
