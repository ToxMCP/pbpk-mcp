from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PBPK_SDK2_", extra="ignore")

    backend_url: str = "http://127.0.0.1:8001"
    bearer_token: SecretStr | None = None
    allowed_hosts: str = "localhost,localhost:*,127.0.0.1,127.0.0.1:*,[::1],[::1]:*"
    allowed_origins: str = (
        "http://localhost,http://localhost:*,http://127.0.0.1,http://127.0.0.1:*,http://[::1],http://[::1]:*"
    )
    max_request_bytes: int = Field(default=4 * 1024 * 1024, gt=0)

    @field_validator("backend_url")
    @classmethod
    def trusted_backend_origin(cls, value):
        parsed = urlsplit(value)
        # Accessing port also rejects malformed or out-of-range authorities.
        _ = parsed.port
        if (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError(
                "Backend must be an origin without credentials, query, fragment or path"
            )
        loopback = parsed.hostname == "localhost"
        try:
            loopback = loopback or ipaddress.ip_address(parsed.hostname or "").is_loopback
        except ValueError:
            pass
        if (
            not parsed.hostname
            or parsed.scheme not in {"http", "https"}
            or (parsed.scheme == "http" and not loopback)
        ):
            raise ValueError("Use HTTPS for a remote backend or HTTP on loopback")
        return value.rstrip("/")

    def hosts(self):
        return [part.strip() for part in self.allowed_hosts.split(",") if part.strip()]

    def origins(self):
        return [part.strip() for part in self.allowed_origins.split(",") if part.strip()]
