"""Readiness tests use synthetic fixtures only; not external/runtime evidence."""
from idp_pegawai.operations.readiness import review_compose, review_gateway, review_oidc


def test_staging_reports_unpinned_dev_keycloak_and_http():
    findings = review_compose({"services": {"kumjabar_keycloak": {
        "image": "quay.io/keycloak/keycloak:latest",
        "command": ["start-dev"], "environment": {"KC_HTTP_ENABLED": "true"}}}})
    assert any("exact-pinned" in item for item in findings)
    assert any("HTTPS" in item for item in findings)


def test_gateway_private_route_requires_tls_and_service_scope():
    findings = review_gateway(
        {"public_ingress": {"allow": ["/oidc/token"]}, "private_ingress":
         {"authentication": "none", "required_scope": ""}},
        {"tls": {"verify_peer": False}},
    )
    assert len(findings) == 2


def test_oidc_fixture_requires_jwks_pkce_state_nonce():
    findings = review_oidc({"jwks": True, "pkce": True})
    assert any("state" in item for item in findings)
    assert any("nonce" in item for item in findings)


def test_private_route_is_not_public_fixture():
    findings = review_gateway(
        {"public_ingress": {"allow": ["/idp-pegawai/internal/*"]}, "private_ingress":
         {"authentication": "service_jwt", "required_scope": "feed:read"}},
        {"tls": {"verify_peer": True}},
    )
    assert any("terbuka" in item for item in findings)
