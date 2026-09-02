"""Fail-closed validation of OIDC JWTs against a supplied JWKS fixture/cache."""
from __future__ import annotations

from typing import Any, Mapping

import jwt
from jwt import InvalidTokenError


class OIDCValidationError(ValueError):
    """Raised when an OIDC token does not meet the consumer contract."""


def validate_token(
    token: str,
    *,
    issuer: str,
    audience: str,
    azp: str,
    jwks: Mapping[str, Any],
    now: int | None = None,
    leeway: int = 0,
) -> dict[str, Any]:
    """Validate a signed JWT using only caller-supplied (normally cached) JWKS.

    Exactly one issuer, audience and authorized party are accepted.  Algorithm
    is deliberately pinned to RS256; no network/JWKS discovery is performed.
    """
    if not isinstance(token, str) or not token:
        raise OIDCValidationError("token tidak valid")
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise OIDCValidationError("algorithm atau kid tidak diizinkan")
        key = jwks[header["kid"]]
        options = {"require": ["iss", "sub", "aud", "azp", "exp", "nbf", "iat"]}
        claims = jwt.decode(
            token, key, algorithms=["RS256"], issuer=issuer, audience=audience,
            options=options, leeway=leeway,
        )
        if claims.get("azp") != azp:
            raise OIDCValidationError("azp tidak cocok")
        if now is not None:
            for name in ("exp", "nbf", "iat"):
                value = claims[name]
                if not isinstance(value, (int, float)):
                    raise OIDCValidationError(f"{name} tidak valid")
            if claims["exp"] <= now - leeway or claims["nbf"] > now + leeway or claims["iat"] > now + leeway:
                raise OIDCValidationError("waktu token tidak valid")
        return dict(claims)
    except OIDCValidationError:
        raise
    except (KeyError, TypeError, InvalidTokenError) as exc:
        raise OIDCValidationError("token OIDC ditolak") from exc
