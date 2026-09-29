from types import SimpleNamespace
from uuid import uuid4


def employee(active=True):
    unit = SimpleNamespace(uuid=uuid4(), code="TUM_TI", name="Unit TI")
    return SimpleNamespace(
        uuid=uuid4(), nama_lengkap="Pegawai Synthetic", status_pegawai="aktif" if active else "nonaktif",
        is_active=active, primary_org_unit=unit,
    )


class ProfileRepo:
    def __init__(self, row=None):
        self.row = row
        self.calls = []

    def get_by_identity_link(self, provider, subject, issuer=None):
        self.calls.append((provider, subject, issuer))
        return self.row


def auth(claims):
    return lambda authorization, headers: claims


def test_profile_returns_curated_active_employee(app):
    repo = ProfileRepo(employee())
    app.config.update(
        TESTING=True, PEGAWAI_REPOSITORY=repo,
        INTERNAL_PROFILE_AUTHORIZER=auth({"iss": "http://issuer", "sub": "subject-1", "aud": "idp-pegawai-internal", "azp": "s1-feed", "scope": "profile:read"}),
    )
    response = app.test_client().get("/idp-pegawai/internal/api/v1/consumer/profile", headers={"Authorization": "Bearer synthetic"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["meta"]["contract_version"] == "pegawai-profile.v1"
    assert payload["data"]["status_pegawai"] == "aktif"
    assert repo.calls == [("keycloak", "subject-1", "http://issuer")]


def test_profile_rejects_missing_or_invalid_service_token(app):
    app.config.update(PEGAWAI_REPOSITORY=ProfileRepo(employee()), INTERNAL_PROFILE_AUTHORIZER=lambda authorization, headers: None)
    response = app.test_client().get("/idp-pegawai/internal/api/v1/consumer/profile")
    assert response.status_code == 401
    assert response.get_json()["code"] == "service_token_invalid"


def test_profile_rejects_inactive_employee(app):
    app.config.update(
        PEGAWAI_REPOSITORY=ProfileRepo(employee(False)),
        INTERNAL_PROFILE_AUTHORIZER=auth({"iss": "http://issuer", "sub": "subject-1", "aud": "idp-pegawai-internal", "azp": "s1-feed", "scope": "profile:read"}),
    )
    response = app.test_client().get("/idp-pegawai/internal/api/v1/consumer/profile", headers={"Authorization": "Bearer synthetic"})
    assert response.status_code == 403
    assert response.get_json()["code"] == "pegawai_inactive"


def test_profile_rejects_wrong_scope(app):
    app.config.update(
        PEGAWAI_REPOSITORY=ProfileRepo(employee()),
        INTERNAL_PROFILE_AUTHORIZER=auth({"iss": "http://issuer", "sub": "subject-1", "aud": "idp-pegawai-internal", "azp": "s1-feed", "scope": "profile:write"}),
    )
    response = app.test_client().get("/idp-pegawai/internal/api/v1/consumer/profile")
    assert response.status_code == 403
    assert response.get_json()["code"] == "consumer_not_allowed"
