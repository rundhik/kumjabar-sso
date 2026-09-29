import pytest

from idp_pegawai.integrations.keycloak.adapter import KeycloakAdapter, KeycloakAdapterError
from idp_pegawai.integrations.keycloak.policy import KeycloakEndpointPolicy


class FakeTransport:
    def __init__(self, representation, token_claims=None):
        self.user = dict(representation)
        self.calls = []
        self.token_claims = token_claims or {"aud": "idp-pegawai-admin", "azp": "idp-pegawai-admin"}
        self.accepted_credential = "good-token"

    def request(self, method, url, *, token, json=None):
        self.calls.append((method, url, token, json))
        if method == "GET":
            return dict(self.user)
        if method == "PUT":
            self.user = dict(json)
            return None
        raise AssertionError(method)


def adapter(transport):
    return KeycloakAdapter(
        KeycloakEndpointPolicy("https://keycloak.example.test", "pegawai", "idp-pegawai-admin"),
        transport,
        credential="good-token",
        expected_audience="idp-pegawai-admin",
    )


def test_get_merge_put_preserves_unmanaged_and_only_manages_fields():
    t = FakeTransport({"id": "u1", "username": "old", "enabled": False, "attributes": {"idp_pegawai_uuid": ["x"], "custom": ["keep"]}, "credentials": [{"type": "password"}], "federatedIdentities": [{"identityProvider": "google"}]})
    result = adapter(t).update_user("u1", {"enabled": True, "attributes": {"idp_pegawai_uuid": ["canonical"]}})
    assert t.calls[0][0] == "GET" and t.calls[1][0] == "PUT" and t.calls[2][0] == "GET"
    sent = t.calls[1][3]
    assert sent["enabled"] is True
    assert sent["attributes"] == {"idp_pegawai_uuid": ["canonical"], "custom": ["keep"]}
    assert "credentials" not in sent and "federatedIdentities" not in sent
    assert result == {"enabled": True, "attributes": {"idp_pegawai_uuid": ["canonical"]}}


def test_managed_field_update_does_not_delete_unmanaged_drift():
    t = FakeTransport({"id": "u1", "attributes": {"custom": ["drift"], "idp_pegawai_uuid": ["x"]}, "enabled": True})
    adapter(t).update_user("u1", {"attributes": {"idp_pegawai_uuid": ["y"]}})
    assert t.user["attributes"]["custom"] == ["drift"]


@pytest.mark.parametrize("claims", [{"aud": "wrong"}, {"azp": "wrong"}])
def test_rejects_wrong_credential_or_audience(claims):
    t = FakeTransport({"id": "u1"}, claims)
    with pytest.raises(KeycloakAdapterError):
        adapter(t).update_user("u1", {"enabled": True})


def test_rejects_wrong_credential_string():
    t = FakeTransport({"id": "u1"})
    with pytest.raises(KeycloakAdapterError):
        KeycloakAdapter(KeycloakEndpointPolicy("https://keycloak.example.test", "pegawai", "idp-pegawai-admin"), t, credential="bad-token", expected_audience="idp-pegawai-admin").update_user("u1", {})


def test_readback_normalizes_attribute_values_and_omits_unmanaged():
    t = FakeTransport({"id": "u1", "enabled": True, "attributes": {"idp_pegawai_uuid": "canonical", "custom": ["x"]}, "realmRoles": ["pegawai", "unmanaged"]})
    assert adapter(t).update_user("u1", {"enabled": True, "attributes": {"idp_pegawai_uuid": ["canonical"]}}) == {"enabled": True, "attributes": {"idp_pegawai_uuid": ["canonical"]}}


def test_empty_managed_update_is_noop_put_still_uses_merge_contract():
    t = FakeTransport({"id": "u1", "enabled": True})
    adapter(t).update_user("u1", {})
    assert [c[0] for c in t.calls] == ["GET", "PUT", "GET"]
