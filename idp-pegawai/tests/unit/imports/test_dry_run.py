from idp_pegawai.imports.dry_run import build_dry_run_plan
from idp_pegawai.imports.validation import validate_rows


def test_dry_run_plans_create_update_noop_reject_without_mutating_snapshot():
    rows = [
        {"nip": "111111111111111111", "nama_lengkap": "Baru", "status_pegawai": "nonaktif"},
        {"nip": "222222222222222222", "nama_lengkap": "Berubah", "status_pegawai": "nonaktif"},
        {"nip": "333333333333333333", "nama_lengkap": "Sama", "status_pegawai": "nonaktif"},
    ]
    existing = {"222222222222222222": {"nip": "222222222222222222", "nama_lengkap": "Lama"}, "333333333333333333": {"nip": "333333333333333333", "nama_lengkap": "Sama", "status_pegawai": "nonaktif"}}
    before = existing.copy()
    validation = validate_rows(rows, org_codes=set())
    plan = build_dry_run_plan(rows, existing, validation)
    assert [item.operation for item in plan.items] == ["planned_create", "planned_update", "planned_noop"]
    assert existing == before
    assert plan.summary["planned_create"] == 1
