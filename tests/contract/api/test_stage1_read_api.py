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
