import pytest

from idp_pegawai.consumer.canonicalize import canonical_hash, canonical_json
from idp_pegawai.consumer.projector import project_snapshot


def test_fixed_profiles_and_no_arbitrary_fields():
    source = {"pegawai_uuid": "ABC", "nama_lengkap": "N", "status_pegawai": "aktif", "is_active": True,
              "primary_org_unit": {"uuid": "U", "code": "TI"}, "nip": "secret"}
    snap = project_snapshot("pegawai", "pegawai.portal-minimal.v1", source, source_version=2,
                            source_updated_at="2026-01-01T00:00:00+00:00")
    assert snap["data"] == {"pegawai_uuid": "abc", "nama_lengkap": "N", "status_pegawai": "aktif", "is_active": True,
                             "primary_org_unit": {"uuid": "u", "code": "TI"}}
    assert "nip" not in snap["data"]
    with pytest.raises(ValueError):
        project_snapshot("pegawai", "pegawai.portal-minimal.v1", source, fields=["nip"])


def test_canonical_hash_is_profile_data_only_and_absent_differs_from_null():
    assert canonical_json({"b": 1, "a": "é"}) == '{"a":"é","b":1}'
    assert canonical_hash({"a": None}) != canonical_hash({})
    snap = project_snapshot("pegawai", "pegawai.portal-minimal.v1", {"pegawai_uuid": "u"}, source_version=1)
    assert snap["payload_hash"] == canonical_hash(snap["data"])


def test_unknown_source_fields_are_not_leaked_and_unknown_profile_rejected():
    with pytest.raises(ValueError):
        project_snapshot("pegawai", "custom.v1", {"pegawai_uuid": "u"})
    snap = project_snapshot("org_unit", "org-unit.navigation.v1", {
        "org_unit_uuid": "U", "code": "X", "name": "Unit", "path": "/x", "is_active": True,
        "internal_secret": "do-not-leak"})
    assert "internal_secret" not in snap["data"]


def test_null_is_preserved_only_when_field_is_present():
    snap = project_snapshot("pegawai", "pegawai.s1-operational.v1",
                            {"pegawai_uuid": "u", "nama_lengkap": None})
    assert snap["data"]["nama_lengkap"] is None
    assert "status_pegawai" not in snap["data"]
    assert "source_updated_at" not in snap["data"]
