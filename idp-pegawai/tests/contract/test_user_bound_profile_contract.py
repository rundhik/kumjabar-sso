"""User-bound profile contract matrix; no real tokens or credentials."""
from types import SimpleNamespace
from uuid import uuid4


def _employee(active=True):
    unit = SimpleNamespace(uuid=uuid4(), code="TUM_TI", name="Unit TI")
    return SimpleNamespace(
        uuid=uuid4(), nama_lengkap="Demo Fixture", status_pegawai="aktif" if active else "nonaktif",
        is_active=active, primary_org_unit=unit,
    )


class _Repo:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def get_by_identity_link(self, provider, subject, issuer=None):
        self.calls.append((provider, subject, issuer))
        return self.row


_DEFAULT = object()


def _app(app, claims, row=_DEFAULT):
    app.config.update(
        TESTING=True,
        PEGAWAI_REPOSITORY=_Repo(_employee() if row is _DEFAULT else row),
        INTERNAL_PROFILE_AUTHORIZER=lambda authorization, headers: claims,
        INTERNAL_PROFILE_CLIENT="s1-jabar-token-exchange",
    )
    if not app.config.get("INTERNAL_PROFILE_REGISTRATIONS"):
        app.config["INTERNAL_PROFILE_REGISTRATIONS"] = {
            "s1-jabar-token-exchange": {
                "status": "active",
                "allowed_resource_families": ["pegawai-profile"],
                "allowed_field_profile": "pegawai-profile.v1",
            }
        }
    return app.test_client()


def _claims(**overrides):
    result = {
        "iss": "http://localhost:8080/realms/kumjabar",
        "sub": "demo-s1-subject-fixture",
        "aud": "idp-pegawai-internal",
        "azp": "s1-jabar-token-exchange",
        "scope": "profile:read",
        "exp": 2_000_000_000,
        "iat": 1_900_000_000,
    }
    result.update(overrides)
    return result


def _get(client):
    return client.get(
        "/idp-pegawai/internal/api/v1/consumer/profile",
        headers={"Authorization": "Bearer redacted-fixture"},
    )


def test_user_bound_active_fixture_returns_200(app):
    response = _get(_app(app, _claims()))
    assert response.status_code == 200
    assert response.get_json()["meta"]["contract_version"] == "pegawai-profile.v1"


def test_user_bound_inactive_fixture_returns_403(app):
    response = _get(_app(app, _claims(), _employee(False)))
    assert response.status_code == 403
    assert response.get_json()["code"] == "pegawai_inactive"


def test_unknown_user_subject_returns_404(app):
    response = _get(_app(app, _claims(), None))
    assert response.status_code == 404
    assert response.get_json()["code"] == "pegawai_identity_not_found"


def test_missing_or_wrong_credential_returns_401(app):
    app.config.update(
        PEGAWAI_REPOSITORY=_Repo(_employee()),
        INTERNAL_PROFILE_AUTHORIZER=lambda authorization, headers: None,
    )
    response = _get(app.test_client())
    assert response.status_code == 401


def test_wrong_scope_returns_403(app):
    response = _get(_app(app, _claims(scope="openid")))
    assert response.status_code == 403
    assert response.get_json()["code"] == "consumer_not_allowed"


def test_wrong_audience_returns_403(app):
    response = _get(_app(app, _claims(aud="another-api")))
    assert response.status_code == 403


def test_wrong_issuer_is_rejected_as_invalid_credential(app):
    app.config.update(
        PEGAWAI_REPOSITORY=_Repo(_employee()),
        INTERNAL_PROFILE_AUTHORIZER=lambda authorization, headers: None,
    )
    response = _get(app.test_client())
    assert response.status_code == 401



def test_wrong_azp_returns_403(app):
    response = _get(_app(app, _claims(azp="other-client")))
    assert response.status_code == 403


def test_registration_must_be_active_and_allow_profile(app):
    app.config["INTERNAL_PROFILE_REGISTRATIONS"] = {
        "s1-jabar-token-exchange": {"status": "proposed", "allowed_resource_families": ["pegawai-profile"], "allowed_field_profile": "pegawai-profile.v1"}
    }
    response = _get(_app(app, _claims()))
    assert response.status_code == 403
    app.config["INTERNAL_PROFILE_REGISTRATIONS"]["s1-jabar-token-exchange"]["status"] = "active"
    response = _get(_app(app, _claims()))
    assert response.status_code == 200


def test_registration_field_profile_is_allowlisted(app):
    app.config["INTERNAL_PROFILE_REGISTRATIONS"] = {
        "s1-jabar-token-exchange": {"status": "active", "allowed_resource_families": ["pegawai-profile"], "allowed_field_profile": "admin-full"}
    }
    response = _get(_app(app, _claims()))
    assert response.status_code == 403
    assert response.get_json()["code"] == "profile_not_allowed"


def test_expired_token_is_rejected_by_authorizer(app):
    app.config.update(
        PEGAWAI_REPOSITORY=_Repo(_employee()),
        INTERNAL_PROFILE_AUTHORIZER=lambda authorization, headers: None,
    )
    response = _get(app.test_client())
    assert response.status_code == 401


def test_forged_identity_context_is_not_taken_from_headers(app):
    repo = _Repo(_employee())
    app.config.update(
        PEGAWAI_REPOSITORY=repo,
        INTERNAL_PROFILE_AUTHORIZER=lambda authorization, headers: _claims(),
        INTERNAL_PROFILE_REGISTRATIONS={
            "s1-jabar-token-exchange": {"status": "active", "allowed_resource_families": ["pegawai-profile"], "allowed_field_profile": "pegawai-profile.v1"}
        },
    )
    response = app.test_client().get(
        "/idp-pegawai/internal/api/v1/consumer/profile",
        headers={"Authorization": "Bearer redacted-fixture", "X-User-Subject": "forged"},
    )
    assert response.status_code == 200
    assert repo.calls == [("keycloak", "demo-s1-subject-fixture", "http://localhost:8080/realms/kumjabar")]