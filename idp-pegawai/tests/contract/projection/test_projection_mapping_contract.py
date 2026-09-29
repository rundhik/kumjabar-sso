from idp_pegawai.projection.mapping_catalog import (
    ATTRIBUTE_CATALOG, GROUP_PREFIX, REALM_ROLE_CATALOG,
)


def test_catalog_is_closed_and_managed_namespace_is_fixed():
    assert GROUP_PREFIX == "/pegawai/kanwil-jabar"
    assert set(ATTRIBUTE_CATALOG) == {
        "idp_pegawai_uuid", "idp_source_version", "user_type", "pegawai_status",
        "primary_org_unit_code", "primary_org_unit_path", "org_unit_codes", "org_group_paths",
    }
    assert REALM_ROLE_CATALOG == frozenset({"pegawai"})
    assert "jabatan" not in ATTRIBUTE_CATALOG
