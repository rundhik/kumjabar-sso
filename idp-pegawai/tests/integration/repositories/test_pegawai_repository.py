import pytest

from idp_pegawai.repositories.pegawai_repository import PegawaiRepository


@pytest.mark.integration
@pytest.mark.postgresql
def test_pegawai_repository_contract_is_query_only():
    assert hasattr(PegawaiRepository, "get_by_uuid")
    assert hasattr(PegawaiRepository, "get_by_nip")
    assert hasattr(PegawaiRepository, "get_by_identity_link")
    assert hasattr(PegawaiRepository, "list_active_snapshot_scope")
    assert not any(name.startswith(("create", "update", "delete")) for name in dir(PegawaiRepository))
