from datetime import datetime, timezone

from idp_pegawai.access.catalog import Role, ScopeType
from idp_pegawai.access.grants import AccessGrant


class Row:
    nip = "NIP-SYNTHETIC"
    nama_lengkap = "Nama Synthetic"
    status_pegawai = "aktif"
    primary_org_unit = None


class Unit:
    code = "ORG-SYNTHETIC"
    name = "Unit Synthetic"
    unit_type = "dinas"
    path = "/synthetic"


class Repo:
    def __init__(self, values=None, error=False):
        self.values, self.error = values or [], error

    def list_active_snapshot_scope(self):
        if self.error:
            raise RuntimeError("backend details must not reach UI")
        return self.values

    def list_active(self):
        if self.error:
            raise RuntimeError("backend details must not reach UI")
        return self.values


def grant():
    return AccessGrant(Role.IMPORT_OPERATOR, ScopeType.GLOBAL)


def test_ui_is_deny_by_default(client):
    for path in ("/ui", "/ui/pegawai", "/ui/organisasi", "/ui/import"):
        response = client.get(path)
        assert response.status_code == 403
        assert b"authorization denied" not in response.data.lower()


def test_authorized_ui_renders_all_read_only_pages(app):
    app.config.update(UI_GRANTS=(grant(),), PEGAWAI_REPOSITORY=Repo([Row()]), ORG_UNIT_REPOSITORY=Repo([Unit()]))
    client = app.test_client()
    assert client.get("/ui").status_code == 200
    assert b"Read-only snapshot" in client.get("/ui").data
    assert b"NIP-SYNTHETIC" in client.get("/ui/pegawai").data
    assert b"ORG-SYNTHETIC" in client.get("/ui/organisasi").data
    import_response = client.get("/ui/import")
    assert import_response.status_code == 200
    assert b"belum mengekspos endpoint upload" not in import_response.data
    assert b"localStorage" not in import_response.data
    assert (b"<form" in import_response.data) if app.config.get("IMPORT_STORAGE_DIR") else b"Import belum tersedia" in import_response.data


def test_ui_renders_empty_and_generic_error_states(app):
    app.config.update(UI_GRANTS=(grant(),), PEGAWAI_REPOSITORY=Repo(), ORG_UNIT_REPOSITORY=Repo())
    client = app.test_client()
    assert b"Belum ada data" in client.get("/ui/pegawai").data
    assert b"Belum ada data" in client.get("/ui/organisasi").data
    app.config.update(PEGAWAI_REPOSITORY=Repo(error=True), ORG_UNIT_REPOSITORY=Repo(error=True))
    assert b"Data sementara tidak tersedia" in client.get("/ui/pegawai").data
    assert b"backend details" not in client.get("/ui/pegawai").data
    assert b"Data sementara tidak tersedia" in client.get("/ui/organisasi").data


def test_ui_static_css_is_served(client):
    response = client.get("/static/ui.css")
    assert response.status_code == 200
    assert b"--brand" in response.data
    assert response.mimetype == "text/css"


def test_ui_templates_do_not_leak_secrets_tokens_or_raw_payloads():
    from pathlib import Path
    root = Path(__file__).parents[2] / "templates/ui"
    text = "\n".join(path.read_text() for path in root.glob("*.html"))
    lowered = text.lower()
    for marker in ("access_token", "refresh_token", "client_secret", "password", "raw_payload", "authorization:"):
        assert marker not in lowered
    assert "import pegawai" in lowered


def test_import_ui_exposes_explicit_workflow_state_controls():
    from pathlib import Path

    template = Path(__file__).parents[2] / "templates/ui/import.html"
    text = template.read_text().lower()
    assert "status-chip" in text
    assert "preview-import" in text
    assert "approve-import" in text
    assert "apply-import" in text
    assert "error-report" in text
