"""Small, transport-injected Keycloak managed-user adapter."""
from __future__ import annotations

from typing import Any

from .policy import KeycloakEndpointPolicy


class KeycloakAdapterError(ValueError):
    """Remote credentials, representation, or contract is invalid."""


class KeycloakAdapter:
    _EXCLUDED = frozenset({"credentials", "federatedIdentities", "access", "clientConsents", "disableableCredentialTypes"})
    _MANAGED = frozenset({"enabled", "attributes"})

    def __init__(self, policy: KeycloakEndpointPolicy, transport: Any, *, credential: str, expected_audience: str):
        self.policy = policy
        self.transport = transport
        self.credential = credential
        self.expected_audience = expected_audience

    def _authorize(self) -> None:
        claims = getattr(self.transport, "token_claims", {})
        accepted = getattr(self.transport, "accepted_credential", self.credential)
        if not self.credential or self.credential != accepted or claims.get("aud") != self.expected_audience or claims.get("azp") != self.expected_audience:
            raise KeycloakAdapterError("credential/audience Keycloak tidak valid")

    @staticmethod
    def _normalize_attributes(value: Any) -> dict[str, list[str]]:
        if not isinstance(value, dict):
            return {}
        return {str(k): (list(v) if isinstance(v, (list, tuple)) else [str(v)]) for k, v in value.items()}

    def _read(self, subject: str) -> dict[str, Any]:
        response = self.transport.request("GET", self.policy.user_url(subject), token=self.credential)
        if not isinstance(response, dict):
            raise KeycloakAdapterError("representasi user Keycloak invalid")
        return response

    def update_user(self, subject: str, managed: dict[str, Any]) -> dict[str, Any]:
        self._authorize()
        current = self._read(subject)
        payload = {k: v for k, v in current.items() if k not in self._EXCLUDED}
        for field in managed:
            if field not in self._MANAGED:
                raise KeycloakAdapterError("field user bukan managed allowlist")
        if "enabled" in managed:
            payload["enabled"] = bool(managed["enabled"])
        if "attributes" in managed:
            attrs = self._normalize_attributes(current.get("attributes"))
            attrs.update(self._normalize_attributes(managed["attributes"]))
            payload["attributes"] = attrs
        self.transport.request("PUT", self.policy.user_url(subject), token=self.credential, json=payload)
        final = self._read(subject)
        result: dict[str, Any] = {}
        if "enabled" in managed:
            result["enabled"] = bool(final.get("enabled"))
        if "attributes" in managed:
            desired_names = set(self._normalize_attributes(managed["attributes"]))
            actual = self._normalize_attributes(final.get("attributes"))
            result["attributes"] = {k: actual.get(k, []) for k in desired_names}
        return result


__all__ = ["KeycloakAdapter", "KeycloakAdapterError"]


assert KeycloakEndpointPolicy
