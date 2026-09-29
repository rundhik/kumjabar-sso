from types import SimpleNamespace
from uuid import UUID

from idp_pegawai import create_app


class FakeOrgUnitRepository:
    def __init__(self):
        self.units = [
            SimpleNamespace(
                uuid=UUID("11111111-1111-1111-1111-111111111111"),
                code="TUM_TI",
                slug="ti",
                name="Teknologi dan Informasi",
                short_name="TI",
                unit_type="tim",
                level=2,
                path="/kanwil-jabar/tum/ti",
                keycloak_group_path="/pegawai/kanwil-jabar/tum/ti",
                sort_order=44,
                is_active=True,
                parent=None,
                children=[],
            )
        ]
        self.calls = []

    def list_active(self):
        self.calls.append("list_active")
        return list(self.units)


def test_get_admin_org_units_has_stable_read_only_contract():
    repository = FakeOrgUnitRepository()
    app = create_app({"TESTING": True, "ORG_UNIT_REPOSITORY": repository})

    response = app.test_client().get("/admin/org-units")

    assert response.status_code == 200
    body = response.get_json()
    assert set(body) == {"data", "sync", "meta"}
    assert body["data"] == [
        {
            "uuid": "11111111-1111-1111-1111-111111111111",
            "code": "TUM_TI",
            "slug": "ti",
            "name": "Teknologi dan Informasi",
            "short_name": "TI",
            "unit_type": "tim",
            "level": 2,
            "path": "/kanwil-jabar/tum/ti",
            "keycloak_group_path": "/pegawai/kanwil-jabar/tum/ti",
            "sort_order": 44,
            "is_active": True,
            "parent": None,
            "children_count": 0,
        }
    ]
    assert body["sync"] == {"source": "idp-pegawai", "contract_version": "org_units.v1"}
    assert body["meta"] == {"count": 1}
    assert repository.calls == ["list_active"]
    assert not hasattr(repository, "save")

    for method in ("post", "put", "delete"):
        assert getattr(app.test_client(), method)("/admin/org-units").status_code == 405


class FakePegawaiRepository:
    def __init__(self):
        self.pegawai = [
            SimpleNamespace(
                uuid=UUID("22222222-2222-2222-2222-222222222222"),
                nip="198001012010011001",
                nama_lengkap="Siti ASN",
                gelar_depan="Dr.",
                gelar_belakang="M.Si.",
                email_dinas="siti@jabarprov.go.id",
                email_google="siti@gmail.com",
                no_hp="08123456789",
                status_pegawai="aktif",
                is_active=True,
                status_reason="rahasia",
                keycloak_user_id="kc-secret",
                primary_org_unit=SimpleNamespace(
                    uuid=UUID("11111111-1111-1111-1111-111111111111"),
                    code="TUM_TI",
                    name="Teknologi dan Informasi",
                ),
            ),
            SimpleNamespace(
                uuid=UUID("33333333-3333-3333-3333-333333333333"),
                nip="198001012010011002",
                nama_lengkap="Budi ASN",
                gelar_depan=None,
                gelar_belakang=None,
                email_dinas=None,
                email_google=None,
                no_hp=None,
                status_pegawai="nonaktif",
                is_active=False,
                status_reason=None,
                keycloak_user_id=None,
                primary_org_unit=None,
            ),
        ]
        self.calls = 0

    def list_active_snapshot_scope(self):
        self.calls += 1
        return list(self.pegawai)


def test_get_admin_pegawai_is_curated_paginated_filterable_and_read_only():
    repository = FakePegawaiRepository()
    app = create_app({"TESTING": True, "PEGAWAI_REPOSITORY": repository})
    client = app.test_client()

    response = client.get("/admin/pegawai?q=siti&page=1&per_page=1")

    assert response.status_code == 200
    body = response.get_json()
    assert set(body) == {"data", "sync", "meta"}
    assert body["data"] == [{
        "uuid": "22222222-2222-2222-2222-222222222222",
        "nip": "198001012010011001",
        "nama_lengkap": "Siti ASN",
        "gelar_depan": "Dr.",
        "gelar_belakang": "M.Si.",
        "status_pegawai": "aktif",
        "is_active": True,
        "primary_org_unit": {"uuid": "11111111-1111-1111-1111-111111111111", "code": "TUM_TI", "name": "Teknologi dan Informasi"},
    }]
    assert body["meta"] == {"page": 1, "per_page": 1, "total": 1, "pages": 1}
    assert body["sync"] == {"source": "idp-pegawai", "contract_version": "pegawai.v1"}
    assert "email_dinas" not in body["data"][0]
    assert "email_google" not in body["data"][0]
    assert "no_hp" not in body["data"][0]
    assert "status_reason" not in body["data"][0]
    assert "keycloak_user_id" not in body["data"][0]
    assert repository.calls == 1
    for method in ("post", "put", "delete"):
        assert getattr(client, method)("/admin/pegawai").status_code == 405


def test_get_admin_pegawai_rejects_unsafe_pagination_and_returns_empty_result():
    repository = FakePegawaiRepository()
    app = create_app({"TESTING": True, "PEGAWAI_REPOSITORY": repository})
    response = app.test_client().get("/admin/pegawai?q=tidak-ada&page=0&per_page=0")

    assert response.status_code == 400
    assert response.get_json() == {"error": "page dan per_page harus bilangan positif"}
    response = app.test_client().get("/admin/pegawai?q=tidak-ada")
    assert response.status_code == 200
    assert response.get_json()["data"] == []
    assert response.get_json()["meta"]["total"] == 0
