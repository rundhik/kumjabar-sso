"""Fixed OIDC claim catalog; callers cannot define arbitrary claim sets."""

from __future__ import annotations


_GLOBAL = frozenset({"iss", "sub", "aud", "azp", "exp", "nbf", "iat"})
_PROFILES = {
    "portal-minimal.v1": _GLOBAL | {"user_type", "pegawai_uuid"},
    "s1-minimal.v1": _GLOBAL | {"user_type", "pegawai_uuid"},
}


def claims_for(profile: str) -> frozenset[str]:
    """Return the immutable, approved claim set for a fixed profile."""
    try:
        return _PROFILES[profile]
    except KeyError as exc:
        raise ValueError("unsupported OIDC claim profile") from exc


def filter_claims(profile: str, claims: dict[str, object]) -> dict[str, object]:
    """Validate and return claims for *profile*, rejecting unknown or missing keys."""
    allowed = claims_for(profile)
    if set(claims) != allowed:
        raise ValueError("claims must exactly match the fixed OIDC catalog")
    return dict(claims)
