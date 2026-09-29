import pytest
from uuid import uuid4
from io import BytesIO
from zipfile import ZipFile


from idp_pegawai.imports.error_workbook import build_error_workbook, escape_formula
from idp_pegawai.imports.apply import atomic_apply
from idp_pegawai.imports.validation import ValidationIssue, ValidationResult


def test_retry_workbook_is_self_contained_and_preserves_canonical_values():
    rows = [{"nip": "123456789012345678", "nama_lengkap": "=Budi", "status_pegawai": "aktif"},
            {"nip": "223456789012345678", "nama_lengkap": "Ani", "status_pegawai": "aktif"}]
    validation = ValidationResult([ValidationIssue("formula_injection_detected", "error", 1, "nama_lengkap", "unsafe")])
    artifact = build_error_workbook(rows, validation, parent_batch_uuid="parent", root_batch_uuid="root")
    assert artifact.profile == "pegawai_error_retry_v1"
    assert set(artifact.sheets) >= {"instructions", "summary", "pegawai", "diagnostics", "reference_status", "reference_org_units", "metadata"}
    assert artifact.sheets["pegawai"][0]["nama_lengkap"] == "=Budi"
    assert artifact.display_sheets["pegawai"][0]["nama_lengkap"] == "'=Budi"
    assert artifact.metadata["parent_batch_uuid"] == "parent"
    assert len(artifact.content) > 0
    with ZipFile(BytesIO(artifact.content)) as package:
        names = set(package.namelist())
        assert "[Content_Types].xml" in names
        assert "_rels/.rels" in names
        assert "xl/_rels/workbook.xml.rels" in names
        assert "xl/workbook.xml" in names
        assert package.testzip() is None


def test_error_workbook_keeps_reference_dropdowns_for_retry():
    artifact = build_error_workbook([], ValidationResult(), parent_batch_uuid="parent", root_batch_uuid="root", org_units=("TUM_TI", "TUM_KEU"))
    from openpyxl import load_workbook
    workbook = load_workbook(BytesIO(artifact.content))
    sheet = workbook["pegawai"]
    formulas = [validation.formula1 for validation in sheet.data_validations.dataValidation]
    assert "=reference!$A$2:$A$6" in formulas
    assert "=reference!$B$2:$B$3" in formulas
    assert workbook["reference"].sheet_state == "hidden"


def test_formula_escape_only_changes_display_value():
    assert escape_formula("=HYPERLINK('x')") == "'=HYPERLINK('x')"
    assert escape_formula("normal") == "normal"
    assert escape_formula(42) == 42


def test_atomic_apply_rolls_back_and_never_leaves_applying():
    state = {"status": "ready_to_apply", "rows": []}
    def mutate():
        state["status"] = "applying"
        state["rows"].append("created")
        raise RuntimeError("constraint")
    with pytest.raises(RuntimeError):
        atomic_apply(state, mutate)
    assert state == {"status": "ready_to_apply", "rows": []}


def test_atomic_apply_commits_terminal_state():
    state = {"status": "ready_to_apply", "rows": []}
    result = atomic_apply(state, lambda: state["rows"].append("created"), success_status="applied")
    assert result is None
    assert state == {"status": "applied", "rows": ["created"]}


def test_retry_lineage_token_is_present_and_unique():
    a = build_error_workbook([], ValidationResult(), parent_batch_uuid=uuid4(), root_batch_uuid=uuid4())
    assert a.metadata["retry_lineage_token"]
    assert a.metadata["retry_lineage_token"] != build_error_workbook([], ValidationResult(), parent_batch_uuid=uuid4(), root_batch_uuid=uuid4()).metadata["retry_lineage_token"]
