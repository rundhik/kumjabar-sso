from types import MappingProxyType

GROUP_PREFIX = "/pegawai/kanwil-jabar"
ATTRIBUTE_CATALOG = frozenset({
    "idp_pegawai_uuid", "idp_source_version", "user_type", "pegawai_status",
    "primary_org_unit_code", "primary_org_unit_path", "org_unit_codes", "org_group_paths",
})
REALM_ROLE_CATALOG = frozenset({"pegawai"})
CLIENT_ROLE_CATALOG = MappingProxyType({})

__all__ = ["GROUP_PREFIX", "ATTRIBUTE_CATALOG", "REALM_ROLE_CATALOG", "CLIENT_ROLE_CATALOG"]
