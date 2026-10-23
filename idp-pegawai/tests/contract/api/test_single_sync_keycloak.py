from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from idp_pegawai import create_app
from idp_pegawai.access.catalog import Role, ScopeType
from idp_pegawai.access.grants import AccessGrant


@pytest.fixture
def app():
    return create_app({
        "TESTING": True,
        "KEYCLOAK_URL": "http://mock-keycloak:8080",
        "KEYCLOAK_REALM": "test-realm",
        "KEYCLOAK_CLIENT_ID": "test-client",
        "KEYCLOAK_CLIENT_SECRET": "test-secret",
        "KEYCLOAK_PUBLIC_URL": "http://localhost:8080",
    })


@pytest.fixture
def sample_emp():
    return SimpleNamespace(
        id=101,
        uuid=UUID("44444444-4444-4444-4444-444444444444"),
        nip="199001012020011001",
        nama_lengkap="Budi Test",
        status_pegawai="aktif",
        is_active=True,
        primary_org_unit=SimpleNamespace(code="UNIT_TEST"),
        email_dinas="budi@kumjabar.go.id",
    )


def test_single_sync_unauthorized(app):
    client = app.test_client()
    # Tanpa grant -> 403
    res = client.post("/admin/pegawai/44444444-4444-4444-4444-444444444444/sync-keycloak")
    assert res.status_code == 403


@patch("idp_pegawai.api.admin._get")
def test_single_sync_not_found(mock_get, app):
    mock_get.return_value = None
    app.config["ADMIN_GRANTS"] = (AccessGrant(Role.ACCESS_ADMIN, ScopeType.GLOBAL),)
    client = app.test_client()

    res = client.post(f"/admin/pegawai/{uuid4()}/sync-keycloak")
    assert res.status_code == 404
    assert res.get_json()["code"] == "not_found"


@patch("idp_pegawai.api.admin._get")
def test_single_sync_invalid_nip(mock_get, app, sample_emp):
    sample_emp.nip = ""
    mock_get.return_value = sample_emp
    app.config["ADMIN_GRANTS"] = (AccessGrant(Role.ACCESS_ADMIN, ScopeType.GLOBAL),)
    client = app.test_client()

    res = client.post(f"/admin/pegawai/{sample_emp.uuid}/sync-keycloak")
    assert res.status_code == 400
    assert res.get_json()["code"] == "invalid_nip"


@patch("idp_pegawai.api.admin.requests.post")
@patch("idp_pegawai.api.admin._get")
def test_single_sync_keycloak_auth_failed(mock_get, mock_post, app, sample_emp):
    mock_get.return_value = sample_emp
    mock_post.return_value = MagicMock(status_code=401, text="Unauthorized")
    app.config["ADMIN_GRANTS"] = (AccessGrant(Role.ACCESS_ADMIN, ScopeType.GLOBAL),)
    client = app.test_client()

    res = client.post(f"/admin/pegawai/{sample_emp.uuid}/sync-keycloak")
    assert res.status_code == 502
    assert res.get_json()["code"] == "kc_auth_failed"


@patch("idp_pegawai.api.admin.db.session")
@patch("idp_pegawai.api.admin._ensure_identity_link")
@patch("idp_pegawai.api.admin.requests.post")
@patch("idp_pegawai.api.admin.requests.get")
@patch("idp_pegawai.api.admin._get")
def test_single_sync_creates_new_user(mock_get_emp, mock_kc_get, mock_kc_post, mock_link, mock_session, app, sample_emp):
    mock_get_emp.return_value = sample_emp
    app.config["ADMIN_GRANTS"] = (AccessGrant(Role.ACCESS_ADMIN, ScopeType.GLOBAL),)
    client = app.test_client()

    # 1. Token response
    token_resp = MagicMock(status_code=200)
    token_resp.json.return_value = {"access_token": "fake-admin-token"}

    # 2. Keycloak GET /users?username=... (user tidak ditemukan)
    check_user_resp = MagicMock(status_code=200)
    check_user_resp.json.return_value = []
    mock_kc_get.return_value = check_user_resp

    # 3. Keycloak POST /users (201 created dengan header Location)
    new_sub = "kc-sub-new-999"
    create_user_resp = MagicMock(
        status_code=201,
        headers={"Location": f"http://mock-keycloak/admin/realms/test-realm/users/{new_sub}"}
    )
    mock_kc_post.side_effect = [token_resp, create_user_resp]

    res = client.post(f"/admin/pegawai/{sample_emp.uuid}/sync-keycloak")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["action"] == "created"
    assert data["keycloak_sub"] == new_sub
    assert data["pegawai_uuid"] == str(sample_emp.uuid)
    assert data["nip"] == sample_emp.nip
    assert data["status"] == "success"

    # Verifikasi _ensure_identity_link dipanggil
    mock_link.assert_called_once_with(sample_emp, new_sub, "http://localhost:8080", "test-realm")


@patch("idp_pegawai.api.admin.db.session")
@patch("idp_pegawai.api.admin._ensure_identity_link")
@patch("idp_pegawai.api.admin.requests.put")
@patch("idp_pegawai.api.admin.requests.get")
@patch("idp_pegawai.api.admin.requests.post")
@patch("idp_pegawai.api.admin._get")
def test_single_sync_updates_existing_user(mock_get_emp, mock_kc_post, mock_kc_get, mock_kc_put, mock_link, mock_session, app, sample_emp):
    mock_get_emp.return_value = sample_emp
    app.config["ADMIN_GRANTS"] = (AccessGrant(Role.ACCESS_ADMIN, ScopeType.GLOBAL),)
    client = app.test_client()

    # Token response
    token_resp = MagicMock(status_code=200)
    token_resp.json.return_value = {"access_token": "fake-admin-token"}
    mock_kc_post.return_value = token_resp

    # User existing di Keycloak
    existing_sub = "existing-sub-888"
    mock_kc_get.return_value = MagicMock(
        status_code=200,
        json=lambda: [{"id": existing_sub, "attributes": {"old_attr": ["123"]}}],
    )

    # PUT user berhasil (204)
    mock_kc_put.return_value = MagicMock(status_code=204)

    res = client.post(f"/admin/pegawai/{sample_emp.uuid}/sync-keycloak")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["action"] == "updated"
    assert data["keycloak_sub"] == existing_sub
    assert data["status"] == "success"

    # Verifikasi _ensure_identity_link dipanggil
    mock_link.assert_called_once_with(sample_emp, existing_sub, "http://localhost:8080", "test-realm")


@patch("idp_pegawai.api.admin.db.session")
@patch("idp_pegawai.api.admin.requests.put")
@patch("idp_pegawai.api.admin.requests.get")
@patch("idp_pegawai.api.admin.requests.post")
@patch("idp_pegawai.api.admin._get")
def test_single_sync_handles_kc_update_failure(mock_get_emp, mock_kc_post, mock_kc_get, mock_kc_put, mock_session, app, sample_emp):
    mock_get_emp.return_value = sample_emp
    app.config["ADMIN_GRANTS"] = (AccessGrant(Role.ACCESS_ADMIN, ScopeType.GLOBAL),)
    client = app.test_client()

    token_resp = MagicMock(status_code=200)
    token_resp.json.return_value = {"access_token": "fake-admin-token"}
    mock_kc_post.return_value = token_resp

    mock_kc_get.return_value = MagicMock(
        status_code=200,
        json=lambda: [{"id": "kc-sub-1", "attributes": {}}],
    )

    mock_kc_put.return_value = MagicMock(status_code=500, text="Internal Keycloak Error")

    res = client.post(f"/admin/pegawai/{sample_emp.uuid}/sync-keycloak")
    assert res.status_code == 502
    assert res.get_json()["code"] == "kc_sync_failed"


def test_ui_pegawai_template_has_single_sync_button():
    from pathlib import Path

    tpl_path = Path(__file__).resolve().parents[3] / "idp_pegawai/templates/ui/pegawai.html"
    content = tpl_path.read_text(encoding="utf-8")

    # Tombol p-sync harus ada di samping tombol edit
    assert "p-sync" in content
    assert "p-edit" in content
    # Aksi klik p-sync memanggil endpoint single sync
    assert "/sync-keycloak" in content
    # Memastikan tidak membocorkan credential di template
    lowered = content.lower()
    for marker in ("access_token", "refresh_token", "client_secret", "password", "raw_payload"):
        assert marker not in lowered

