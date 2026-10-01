"""Real signing keys exercise production JWT validation after backend migration."""

from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from mcp_bridge.config import AppConfig
from mcp_bridge.security import auth


@pytest.fixture(scope="module")
def signing_keys():
    keys = [rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2)]
    jwks = []
    for index, key in enumerate(keys):
        public = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
        public.update(kid=f"key-{index}", use="sig", alg="RS256")
        jwks.append(public)
    return keys, jwks


@pytest.fixture
def validator(monkeypatch, signing_keys):
    monkeypatch.setattr(auth, "_JWT_BACKEND", None)
    monkeypatch.setattr(auth, "_get_jwks", lambda *_args: {"keys": signing_keys[1]})
    config = AppConfig(
        environment="production",
        auth_issuer_url="https://issuer.example",
        auth_jwks_url="https://issuer.example/jwks",
        auth_audience="pbpk",
    )
    return auth.JWTValidator(config)


def token(key, *, kid="key-0", **overrides):
    now = int(time.time())
    claims = {
        "sub": "scientist",
        "roles": ["viewer"],
        "iss": "https://issuer.example",
        "aud": "pbpk",
        "iat": now,
        "exp": now + 300,
        **overrides,
    }
    claims = {name: value for name, value in claims.items() if value is not None}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


def test_trusted_rsa_keys_and_rotation(validator, signing_keys):
    keys, _jwks = signing_keys
    for index, key in enumerate(keys):
        context = validator.validate(token(key, kid=f"key-{index}"))
        assert context.subject == "scientist"
        assert context.roles == ["viewer"]


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://wrong.example"},
        {"aud": "wrong"},
        {"exp": 1},
        {"exp": None},
        {"sub": None},
        {"nbf": int(time.time()) + 3600},
    ],
)
def test_invalid_registered_claims_are_rejected(validator, signing_keys, claims):
    with pytest.raises(auth.AuthError) as error:
        validator.validate(token(signing_keys[0][0], **claims))
    assert error.value.status_code == 401


def test_untrusted_signature_and_unknown_key_are_rejected(validator, signing_keys):
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    for encoded in [token(wrong_key), token(signing_keys[0][0], kid="unknown")]:
        with pytest.raises(auth.AuthError) as error:
            validator.validate(encoded)
        assert error.value.status_code == 401


def test_hmac_cannot_substitute_for_production_rsa(validator):
    encoded = jwt.encode(
        {"sub": "attacker", "iss": "https://issuer.example", "aud": "pbpk", "exp": 1},
        "a-development-secret-that-is-long-enough",
        algorithm="HS256",
        headers={"kid": "key-0"},
    )
    with pytest.raises(auth.AuthError):
        validator.validate(encoded)


@pytest.mark.parametrize("encoded", ["bad", "e30.e30.bad", "", "not.a.jwt.token"])
def test_malformed_tokens_are_auth_errors(validator, encoded):
    with pytest.raises(auth.AuthError) as error:
        validator.validate(encoded)
    assert error.value.status_code == 401


def test_single_key_without_kid_remains_supported(monkeypatch, validator, signing_keys):
    key = signing_keys[0][0]
    monkeypatch.setattr(auth, "_get_jwks", lambda *_args: {"keys": [signing_keys[1][0]]})
    encoded = jwt.encode(
        {
            "sub": "scientist",
            "iss": "https://issuer.example",
            "aud": "pbpk",
            "exp": int(time.time()) + 60,
        },
        key,
        algorithm="RS256",
    )
    assert validator.validate(encoded).subject == "scientist"


def test_rotating_keys_without_kid_remain_supported(validator, signing_keys):
    for key in signing_keys[0]:
        encoded = jwt.encode(
            {
                "sub": "scientist",
                "iss": "https://issuer.example",
                "aud": "pbpk",
                "exp": int(time.time()) + 60,
            },
            key,
            algorithm="RS256",
        )
        assert validator.validate(encoded).subject == "scientist"

    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(auth.AuthError):
        validator.validate(jwt.encode({"sub": "attacker"}, wrong_key, algorithm="RS256"))
