"""Safe non-production Keycloak evidence probe.

The probe reads credentials from the process environment only. It never returns,
logs, or serializes the client secret or access token.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from .policy import KeycloakEndpointPolicy
from .transport import KeycloakHTTPTransport, KeycloakTransportError


@dataclass(frozen=True)
class KeycloakEvidence:
    token_http_status: int
    users_http_status: int
    synthetic_user_checked: bool = False


def _required_env() -> dict[str, str] | None:
    names = ("KEYCLOAK_URL", "KEYCLOAK_REALM", "KEYCLOAK_CLIENT_ID", "KEYCLOAK_CLIENT_SECRET")
    values = {name: os.environ.get(name, "") for name in names}
    return values if all(values.values()) else None


def run_nonproduction_probe(*, synthetic_user_id: str | None = None) -> KeycloakEvidence:
    """Obtain client credentials and GET admin users, without exposing secrets.

    This intentionally does not load ``.env`` and only permits explicit dev HTTP.
    The transport currently abstracts response status, so successful responses are
    represented as 200; HTTP errors are raised by urllib and become a safe error.
    """
    values = _required_env()
    if values is None:
        raise KeycloakTransportError("environment Keycloak evidence tidak lengkap")
    parsed = urlsplit(values["KEYCLOAK_URL"])
    if parsed.scheme == "http" and os.environ.get("KEYCLOAK_ALLOW_INSECURE_DEV", "").lower() not in {"1", "true", "yes", "on"}:
        raise KeycloakTransportError("HTTP hanya boleh dengan KEYCLOAK_ALLOW_INSECURE_DEV eksplisit")
    policy = KeycloakEndpointPolicy(
        values["KEYCLOAK_URL"], values["KEYCLOAK_REALM"], values["KEYCLOAK_CLIENT_ID"],
        allow_insecure_dev=parsed.scheme == "http",
    )
    transport = KeycloakHTTPTransport(policy, client_id=values["KEYCLOAK_CLIENT_ID"], client_secret=values["KEYCLOAK_CLIENT_SECRET"])
    token = transport._access_token()
    if not token:
        raise KeycloakTransportError("token Keycloak tidak tersedia")
    transport.request("GET", policy._url("users"))
    checked = synthetic_user_id is not None
    if synthetic_user_id is not None:
        transport.request("GET", policy.user_url(synthetic_user_id))
    return KeycloakEvidence(200, 200, checked)


__all__ = ["KeycloakEvidence", "run_nonproduction_probe"]
