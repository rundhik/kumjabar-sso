#!/usr/bin/env python3
"""Safe local integration runner for the s1-jabar user-bound profile pilot.

Secrets/tokens are read only from the environment (or an injected secret store)
and are never printed. The runner does not mint JWTs and never trusts a raw
subject header. It requires an existing user token for the exchange.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


RUNNER_NAME = "s1-jabar-user-bound-profile"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def emit(**values: Any) -> None:
    for key, value in values.items():
        print(f"{key}={value}")


def request_json(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=float(env("S1_PROFILE_TIMEOUT_SECONDS", "10"))) as response:
            raw = response.read()
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                body = {}
            return response.status, body if isinstance(body, dict) else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            body = {}
        return exc.code, body if isinstance(body, dict) else {}
    except (urllib.error.URLError, TimeoutError):
        return 503, {}


def token_exchange() -> tuple[str | None, str | None]:
    user_token = env("S1_USER_ACCESS_TOKEN")
    if not user_token:
        return None, "missing_user_token"
    endpoint = env("KEYCLOAK_TOKEN_ENDPOINT")
    requester_id = env("S1_TOKEN_EXCHANGE_CLIENT_ID")
    requester_secret = env("S1_TOKEN_EXCHANGE_CLIENT_SECRET")
    target_client = env("S1_TOKEN_EXCHANGE_TARGET_CLIENT", "idp-pegawai-internal")
    if not endpoint or not requester_id or not requester_secret:
        return None, "missing_exchange_configuration"
    form = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": user_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "audience": target_client,
        "scope": env("S1_PROFILE_SCOPE", "profile:read"),
    }).encode()
    basic = urllib.parse.quote(requester_id, safe="") + ":" + urllib.parse.quote(requester_secret, safe="")
    # Basic value is generated locally and never emitted.
    auth = __import__("base64").b64encode(basic.encode()).decode()
    status, body = request_json(endpoint, method="POST", data=form, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": "Basic " + auth,
    })
    access_token = body.get("access_token") if isinstance(body, dict) else None
    if status != 200 or not isinstance(access_token, str) or not access_token:
        return None, f"token_exchange_http_{status}"
    return access_token, None


def main() -> int:
    emit(runner_name=RUNNER_NAME, active_fixture="available" if env("S1_USER_ACCESS_TOKEN") else "unavailable", negative_fixtures="not_available", output_format="available")
    token, error = token_exchange()
    if not token:
        emit(integration_test="not_available", active_status="not_available", active_contract="", profile_code=error or "token_exchange_failed", exit_code=2)
        return 2
    profile_url = env("IDP_PROFILE_URL", "http://kumjabar_idp:9999/idp-pegawai/internal/api/v1/consumer/profile")
    status, body = request_json(profile_url, headers={
        "Authorization": "Bearer " + token,
        "X-Consumer-Code": env("S1_CONSUMER_CODE", "s1-jabar-token-exchange"),
        "Accept": "application/json",
    })
    data = body.get("data") if isinstance(body, dict) else {}
    meta = body.get("meta") if isinstance(body, dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    code = body.get("code", "") if isinstance(body, dict) else ""
    if status != 200 and not code:
        code = body.get("error", "") if isinstance(body, dict) else ""
    passed = status == 200 and meta.get("contract_version") == "pegawai-profile.v1" and isinstance(data, dict)
    emit(integration_test="passed" if passed else "failed", active_status=status, active_contract=meta.get("contract_version", ""), profile_code=code, identity_resolution="provider+issuer+provider_subject", exit_code=0 if passed else 1)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
