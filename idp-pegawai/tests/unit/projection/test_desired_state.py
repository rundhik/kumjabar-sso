from types import SimpleNamespace
from uuid import uuid4

import pytest

from idp_pegawai.projection.desired_state import DesiredStateResolver, ProjectionContractError


def employee(*, active=True, org=None):
    return SimpleNamespace(
        uuid=uuid4(), status_pegawai="aktif" if active else "nonaktif",
        is_active=active, primary_org_unit=org, metadata_={"source_version": 7},
    )


def unit():
    return SimpleNamespace(uuid=uuid4(), code="TUM_TI", path="/kanwil-jabar/tum/ti",
                           keycloak_group_path="/pegawai/kanwil-jabar/tum/ti", is_active=True)


def test_resolves_only_catalogled_attributes_and_canonical_org_group():
    emp = employee(org=unit())
    state = DesiredStateResolver().resolve(emp)
    assert state.managed_attributes["idp_pegawai_uuid"] == [str(emp.uuid)]
    assert state.managed_attributes["org_group_paths"] == ["/pegawai/kanwil-jabar/tum/ti"]
    assert state.managed_groups[0]["path"] == emp.primary_org_unit.keycloak_group_path
    assert "jabatan" not in state.to_dict()


def test_jabatan_does_not_create_role_and_only_managed_role_is_pegawai():
    emp = employee(org=unit())
    emp.jabatan = "Kepala"
    state = DesiredStateResolver().resolve(emp)
    assert state.managed_realm_roles == ["pegawai"]
    assert state.managed_client_roles == {}


def test_rejects_arbitrary_remote_mapping_and_claims():
    with pytest.raises(ProjectionContractError):
        DesiredStateResolver().resolve(employee(org=unit()), remote_group_path="/admin", claims={"x": ["y"]})


def test_inactive_has_no_group_or_role_and_missing_active_org_is_rejected():
    state = DesiredStateResolver().resolve(employee(active=False))
    assert state.account["enabled"] is False
    assert state.managed_groups == []
    assert state.managed_realm_roles == []
    with pytest.raises(ProjectionContractError):
        DesiredStateResolver().resolve(employee(active=True))


def test_org_path_must_be_canonical_managed_path():
    bad = unit(); bad.keycloak_group_path = "/other/unit"
    with pytest.raises(ProjectionContractError):
        DesiredStateResolver().resolve(employee(org=bad))
