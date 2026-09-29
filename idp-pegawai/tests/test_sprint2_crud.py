from types import SimpleNamespace

import pytest

from idp_pegawai.services.org_unit_service import OrgUnitService
from idp_pegawai.services.pegawai_service import PegawaiService


class Session:
    def add(self, obj):
        self.obj = obj


def test_org_unit_update_changes_mutable_fields():
    unit = SimpleNamespace(name="Lama", short_name=None, uuid="u", id=1)
    result = OrgUnitService(Session()).update(unit, name="Baru", short_name="B")
    assert result is unit
    assert (unit.name, unit.short_name) == ("Baru", "B")


def test_org_unit_deactivate_is_non_destructive():
    unit = SimpleNamespace(is_active=True, metadata_={})
    OrgUnitService(Session()).deactivate(unit, "restrukturisasi")
    assert unit.is_active is False
    assert unit.metadata_["deactivation_reason"] == "restrukturisasi"


def test_pegawai_deactivate_sets_status_and_effective_date():
    pegawai = SimpleNamespace(status_pegawai="aktif", is_active=True, status_reason=None, status_effective_at=None)
    result = PegawaiService(Session()).deactivate(pegawai, reason="pensiun")
    assert result is pegawai
    assert pegawai.status_pegawai == "nonaktif"
    assert pegawai.is_active is False
    assert pegawai.status_reason == "pensiun"
    assert pegawai.status_effective_at is not None


def test_pegawai_deactivate_rejects_active_status():
    pegawai = SimpleNamespace()
    with pytest.raises(ValueError, match="status deaktif"):
        PegawaiService(Session()).deactivate(pegawai, "aktif")


def test_org_unit_update_does_not_change_identity_fields():
    unit = SimpleNamespace(uuid="u", id=1, parent_id=2, name="Lama")
    OrgUnitService(Session()).update(unit, uuid="new", id=9, parent_id=8, name="Baru")
    assert (unit.uuid, unit.id, unit.parent_id, unit.name) == ("u", 1, 2, "Baru")


def test_pegawai_create_normalizes_emails_and_adds_object():
    session = Session()
    from idp_pegawai.models.org_unit import OrgUnit
    org = OrgUnit(code="U", slug="u", name="Unit", unit_type="bidang", level=0,
                  path="/u", keycloak_group_path="/pegawai/u")
    obj = PegawaiService(session).create(
        nip="123456789012345678", nama_lengkap="A", status_pegawai="aktif",
        is_active=True, primary_org_unit=org, email_dinas="  A@EXAMPLE.COM ",
    )
    assert session.obj is obj
    assert obj.email_dinas_normalized == "a@example.com"
