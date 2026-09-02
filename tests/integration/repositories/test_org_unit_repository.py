import pytest

from idp_pegawai.repositories.org_unit_repository import OrgUnitRepository


@pytest.mark.integration
@pytest.mark.postgresql
def test_org_unit_repository_contract_is_query_only():
    assert hasattr(OrgUnitRepository, "get_by_uuid")
    assert hasattr(OrgUnitRepository, "get_by_code")
    assert hasattr(OrgUnitRepository, "get_by_path")
    assert hasattr(OrgUnitRepository, "list_children")
    assert hasattr(OrgUnitRepository, "list_active")
    assert not any(name.startswith(("create", "update", "delete")) for name in dir(OrgUnitRepository))
