import pytest

from idp_pegawai.integrations.keycloak.adapter import KeycloakAdapter
from idp_pegawai.integrations.keycloak.policy import KeycloakEndpointPolicy
from idp_pegawai.integrations.keycloak.reconciliation import reconcile


class FakeTransport:
    def __init__(self, user):
        self.user = dict(user)
        self.calls = []
        self.token_claims = {"aud": "idp-pegawai-admin", "azp": "idp-pegawai-admin"}
        self.accepted_credential = "good-token"

    def request(self, method, url, *, token, json=None):
        self.calls.append((method, url, token, json))
        if method == "GET":
            return dict(self.user)
        self.user = dict(json)
        return None


def make(user):
    t = FakeTransport(user)
    a = KeycloakAdapter(KeycloakEndpointPolicy("https://kc.test", "pegawai", "idp-pegawai-admin"), t, credential="good-token", expected_audience="idp-pegawai-admin")
    return a, t


def test_match_is_in_sync_after_normalized_readback():
    a, t = make({"id": "u1", "attributes": {"idp_pegawai_uuid": [" x ", "x"], "custom": ["drift"]}, "enabled": True})
    result = reconcile(a, "u1", {"idp_pegawai_uuid": ["x"]}, expected_identity="x")
    assert result.status == "in_sync"
    assert result.managed_drift == {}
    assert [c[0] for c in t.calls] == ["GET"]


def test_managed_drift_is_repaired_and_reported_unmanaged_preserved():
    a, t = make({"id": "u1", "attributes": {"idp_pegawai_uuid": ["x"], "user_type": ["old"], "custom": ["keep"]}, "enabled": True})
    result = reconcile(a, "u1", {"idp_pegawai_uuid": ["x"], "user_type": ["new"]}, expected_identity="x")
    assert result.status == "repaired"
    assert result.managed_drift == {"user_type": {"actual": ["old"], "desired": ["new"]}}
    assert result.unmanaged_drift == {"custom": ["keep"]}
    assert t.user["attributes"]["custom"] == ["keep"]


def test_identity_mismatch_fails_closed_without_mutation():
    a, t = make({"id": "u1", "attributes": {"idp_pegawai_uuid": ["other"]}, "enabled": False})
    result = reconcile(a, "u1", {"idp_pegawai_uuid": ["wanted"]}, expected_identity="wanted")
    assert result.status == "blocked_identity_mismatch"
    assert [c[0] for c in t.calls] == ["GET"]


def test_bad_credentials_fail_closed():
    a, _ = make({"id": "u1"})
    a.credential = "bad"
    with pytest.raises(Exception):
        reconcile(a, "u1", {}, expected_identity=None)
