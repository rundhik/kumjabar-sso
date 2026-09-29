import pytest

from idp_pegawai.integrations.keycloak.policy import KeycloakEndpointPolicy, KeycloakPolicyError


def test_builds_only_configured_realm_and_client_endpoint():
    policy = KeycloakEndpointPolicy("https://keycloak.example.test/", "pegawai", "idp-pegawai-admin:user")
    assert policy.user_url("user/with?unsafe") == (
        "https://keycloak.example.test/admin/realms/pegawai/users/user%2Fwith%3Funsafe"
    )
    assert policy.client_url() == (
        "https://keycloak.example.test/admin/realms/pegawai/clients/idp-pegawai-admin%3Auser"
    )


@pytest.mark.parametrize("base", [
    "http://keycloak.example.test",
    "https://127.0.0.1",
    "https://10.0.0.1/kc",
    "https://[::1]",

])
def test_rejects_non_https_or_untrusted_ssrf_targets(base):
    with pytest.raises(KeycloakPolicyError):
        KeycloakEndpointPolicy(base, "pegawai", "client")


def test_rejects_free_text_realm_client_and_endpoint_components():
    with pytest.raises(KeycloakPolicyError):
        KeycloakEndpointPolicy("https://keycloak.example.test", "pegawai/other", "client")
    with pytest.raises(KeycloakPolicyError):
        KeycloakEndpointPolicy("https://keycloak.example.test", "pegawai", "client/other")


def test_request_contract_has_no_url_override():
    policy = KeycloakEndpointPolicy("https://keycloak.example.test", "pegawai", "client")
    request = policy.user_request("abc")
    assert request == {"method": "GET", "url": policy.user_url("abc")}
    assert "url" not in {"method": "GET"}  # callers cannot supply a free-text URL


def test_remote_execution_is_explicitly_outside_domain_transaction():
    policy = KeycloakEndpointPolicy("https://keycloak.example.test", "pegawai", "client")
    assert policy.remote_call_allowed(in_domain_transaction=False)
    assert not policy.remote_call_allowed(in_domain_transaction=True)


def test_rejects_query_fragment_and_credentials_in_endpoint():
    for base in (
        "https://user:pass@keycloak.example.test",
        "https://keycloak.example.test?x=1",
        "https://keycloak.example.test/#x",
    ):
        with pytest.raises(KeycloakPolicyError):
            KeycloakEndpointPolicy(base, "pegawai", "client")


def test_empty_or_invalid_subject_rejected():
    policy = KeycloakEndpointPolicy("https://keycloak.example.test", "pegawai", "client")
    with pytest.raises(KeycloakPolicyError):
        policy.user_url("")
    with pytest.raises(KeycloakPolicyError):
        policy.user_url("../secret")


def test_only_allowlisted_host_is_accepted():
    policy = KeycloakEndpointPolicy(
        "https://keycloak.example.test", "pegawai", "client", allowed_hosts={"keycloak.example.test"}
    )
    assert policy.base_url == "https://keycloak.example.test"
    with pytest.raises(KeycloakPolicyError):
        KeycloakEndpointPolicy("https://other.example.test", "pegawai", "client", allowed_hosts={"keycloak.example.test"})
