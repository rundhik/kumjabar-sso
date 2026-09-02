"""Pure projector for the Phase 5.1 canonical consumer snapshot."""
from .canonicalize import canonical_hash, canonical_timestamp
from .profiles import fields_for


def _lower_uuid(value):
    return value.lower() if isinstance(value, str) else value


def project_snapshot(resource_type, profile, source, *, source_version=None,
                     source_updated_at=None, fields=None):
    if fields is not None:
        raise ValueError("arbitrary fields are not supported")
    allowed = fields_for(profile, resource_type)
    data = {}
    for key in allowed:
        if key in source:
            value = source[key]
            if key.endswith("uuid") or key == "pegawai_uuid":
                value = _lower_uuid(value)
            elif key == "primary_org_unit" and isinstance(value, dict):
                value = {k: (_lower_uuid(v) if k == "uuid" else v)
                         for k, v in value.items() if k in {"uuid", "code"}}
            data[key] = value
    result = {
        "contract_version": "pegawai-consumer.v1" if resource_type == "pegawai" else "org-unit-consumer.v1",
        "field_profile": profile,
        "resource_type": resource_type,
        "data": data,
        "payload_hash": canonical_hash(data),
    }
    if source_version is not None:
        result["source_version"] = source_version
    if source_updated_at is not None:
        result["source_updated_at"] = canonical_timestamp(source_updated_at)
    if "pegawai_uuid" in data:
        result["resource_uuid"] = data["pegawai_uuid"]
    elif "org_unit_uuid" in data:
        result["resource_uuid"] = data["org_unit_uuid"]
    return result

project = project_snapshot
