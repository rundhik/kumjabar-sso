"""Minimal HTTP transport for Keycloak client-credentials and admin API."""
from __future__ import annotations
import json
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

class KeycloakTransportError(RuntimeError):
    """Transport failure without exposing credentials."""

class KeycloakHTTPTransport:
    def __init__(self, policy, *, client_id: str, client_secret: str, timeout: float = 10.0, opener=urlopen):
        if not client_id or not client_secret:
            raise KeycloakTransportError("client credentials Keycloak wajib dikonfigurasi")
        self.policy, self.client_id, self._secret = policy, client_id, client_secret
        self.timeout, self._opener, self._token, self._expires_at = timeout, opener, None, 0.0

    def _access_token(self):
        if self._token and time.monotonic() < self._expires_at - 10:
            return self._token
        body = urlencode({"grant_type":"client_credentials", "client_id":self.client_id, "client_secret":self._secret}).encode()
        req = Request(self.policy.base_url + "/realms/" + self.policy.realm + "/protocol/openid-connect/token", data=body, headers={"Content-Type":"application/x-www-form-urlencoded"}, method="POST")
        try:
            with self._opener(req, timeout=self.timeout) as response: data = json.loads(response.read())
        except Exception as exc: raise KeycloakTransportError("gagal memperoleh token Keycloak") from exc
        if not data.get("access_token"): raise KeycloakTransportError("respons token Keycloak invalid")
        self._token, self._expires_at = data["access_token"], time.monotonic() + int(data.get("expires_in", 60))
        return self._token

    def request(self, method, url, *, token=None, json=None):
        headers = {"Accept":"application/json", "Authorization":"Bearer " + (token or self._access_token())}
        data = None
        if json is not None:
            headers["Content-Type"] = "application/json"; data = __import__("json").dumps(json).encode()
        try:
            with self._opener(Request(url, data=data, headers=headers, method=method), timeout=self.timeout) as response:
                raw = response.read(); return __import__("json").loads(raw) if raw else None
        except Exception as exc: raise KeycloakTransportError("request Keycloak gagal") from exc
