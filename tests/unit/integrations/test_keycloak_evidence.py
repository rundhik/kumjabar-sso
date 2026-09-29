import pytest

from idp_pegawai.integrations.keycloak import evidence
from idp_pegawai.integrations.keycloak.transport import KeycloakTransportError


def test_probe_requires_environment_without_reading_dotenv(monkeypatch):
    for name in ("KEYCLOAK_URL", "KEYCLOAK_REALM", "KEYCLOAK_CLIENT_ID", "KEYCLOAK_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(KeycloakTransportError, match="environment Keycloak evidence tidak lengkap"):
        evidence.run_nonproduction_probe()


def test_probe_is_explicit_about_dev_http(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak.test")
    monkeypatch.setenv("KEYCLOAK_REALM", "kumjabar")
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "idp-pegawai-admin")
    monkeypatch.setenv("KEYCLOAK_CLIENT_SECRET", "synthetic-secret")
    monkeypatch.delenv("KEYCLOAK_ALLOW_INSECURE_DEV", raising=False)
    with pytest.raises(KeycloakTransportError, match="HTTP hanya boleh"):
        evidence.run_nonproduction_probe()
