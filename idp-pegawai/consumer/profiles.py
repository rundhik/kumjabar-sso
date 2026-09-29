"""Reviewed, fixed consumer field profiles (never caller-selectable)."""

PROFILES = {
    "pegawai.portal-minimal.v1": {
        "pegawai_uuid", "nama_lengkap", "status_pegawai", "is_active", "primary_org_unit"
    },
    "pegawai.s1-operational.v1": {
        "pegawai_uuid", "nama_lengkap", "status_pegawai", "is_active", "primary_org_unit", "org_affiliations"
    },
    "org-unit.navigation.v1": {
        "org_unit_uuid", "code", "name", "short_name", "unit_type", "parent_org_unit_uuid",
        "path", "is_active", "level", "sort_order"
    },
}

RESOURCE_PROFILES = {
    name: ("org_unit" if name.startswith("org-unit.") else "pegawai") for name in PROFILES
}

def fields_for(profile: str, resource_type: str) -> set[str]:
    if profile not in PROFILES or RESOURCE_PROFILES[profile] != resource_type:
        raise ValueError("unsupported consumer profile")
    return PROFILES[profile]
