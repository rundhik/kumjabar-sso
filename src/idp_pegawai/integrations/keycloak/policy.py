"""Closed Keycloak endpoint and request policy (no caller-controlled URLs)."""
from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import quote, urlsplit


class KeycloakPolicyError(ValueError):
    """Configuration or request violates the Keycloak boundary."""


@dataclass(frozen=True)
class KeycloakEndpointPolicy:
    base_url: str
    realm: str
    client: str
    allowed_hosts: frozenset[str] | set[str] | None = None

    def __post_init__(self) -> None:
        parsed = urlsplit(self.base_url)
        host = parsed.hostname
        if parsed.scheme != "https" or not host or parsed.username or parsed.password:
            raise KeycloakPolicyError("Keycloak endpoint harus HTTPS tanpa kredensial")
        if parsed.query or parsed.fragment or parsed.port not in (None, 443):
            raise KeycloakPolicyError("Keycloak endpoint memiliki komponen terlarang")
        try:
            ip = ip_address(host)
        except ValueError:
            ip = None
        if ip is not None and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved):
            raise KeycloakPolicyError("target Keycloak tidak boleh alamat internal")
        allowed = self.allowed_hosts
        if allowed is not None and host.lower() not in {h.lower() for h in allowed}:
            raise KeycloakPolicyError("host Keycloak di luar allowlist")
        if not self._component(self.realm) or not self._component(self.client):
            raise KeycloakPolicyError("realm/client harus identifier terkonfigurasi")
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))

    @staticmethod
    def _component(value: str) -> bool:
        return bool(value) and all(c.isalnum() or c in "._:-" for c in value)

    def _url(self, *parts: str) -> str:
        return self.base_url + "/admin/realms/" + quote(self.realm, safe="") + "/" + "/".join(quote(p, safe="") for p in parts)

    def user_url(self, subject: str) -> str:
        if not subject or subject in (".", "..") or "\\" in subject or any(part in (".", "..") for part in subject.split("/")):
            raise KeycloakPolicyError("subject Keycloak tidak valid")
        return self._url("users", subject)

    def client_url(self) -> str:
        return self._url("clients", self.client)

    def user_request(self, subject: str) -> dict[str, str]:
        return {"method": "GET", "url": self.user_url(subject)}

    @staticmethod
    def remote_call_allowed(*, in_domain_transaction: bool) -> bool:
        return not in_domain_transaction


__all__ = ["KeycloakEndpointPolicy", "KeycloakPolicyError"]

ClientPolicy = KeycloakEndpointPolicy
RequestPolicy = KeycloakEndpointPolicy
