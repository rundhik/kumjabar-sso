import pytest
from idp_pegawai.imports.validation import validate_rows, ValidationIssue


def row(nip="123456789012345678", **kw):
    return {"nip": nip, "nama_lengkap": "Ani", "org_unit_code": "ORG1", "status_pegawai": "aktif", **kw}


def test_validation_catalogs_duplicates_unknown_org_lifecycle_and_forbidden_formula():
    result = validate_rows([row(), row(), row(nip="=1+1", status_pegawai="mutasi")], org_codes={"ORG1"})
    codes = {i.code for i in result.issues}
    assert {"duplicate_nip_in_file", "nip_format_invalid", "status_pegawai_invalid"} <= codes
    assert result.blocking


def test_validation_warns_active_without_email_and_forbidden_header_is_fatal():
    result = validate_rows([row()], org_codes={"ORG1"}, headers=["nip", "nama_lengkap", "jabatan"])
    assert any(i.code == "forbidden_header" and i.severity == "fatal" for i in result.issues)
    assert any(i.code == "active_pegawai_without_email" and i.severity == "warning" for i in result.issues)


def test_validation_rejects_unknown_org_and_inconsistent_active_flag():
    result = validate_rows([row(org_unit_code="NOPE", is_active=False)], org_codes={"ORG1"})
    assert {i.code for i in result.issues} >= {"org_unit_code_not_found", "inactive_status_with_active_eligibility"}


def test_error_catalog_is_bounded():
    assert ValidationIssue.CODES
    assert all(i.code in ValidationIssue.CODES for i in validate_rows([row()], {"ORG1"}).issues)
