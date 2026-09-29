import pytest
from types import SimpleNamespace

from idp_pegawai.models import OrgUnit
from idp_pegawai.services import OrgUnitSeedService, OrgUnitService, PegawaiService


class FakeSession:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)

    def flush(self):
        return None

    def query(self, model):
        session = self
        class Query:
            def filter_by(self, **filters):
                self.filters = filters
                return self
            def one_or_none(self):
                return next((x for x in session.items if all(getattr(x, k, None) == v for k, v in self.filters.items())), None)
        return Query()


def unit(code="KANWIL_JABAR", slug="kanwil-jabar", name="Kanwil Jawa Barat"):
    return dict(code=code, slug=slug, name=name, unit_type="kanwil", level=0,
                path=f"/{slug}", keycloak_group_path=f"/pegawai/{slug}")


def test_org_service_rejects_inconsistent_paths():
    with pytest.raises(ValueError, match="path"):
        OrgUnitService(FakeSession()).create(**{**unit(), "path": "/wrong"})


def test_pegawai_service_normalizes_email_and_deactivates_without_delete():
    session = FakeSession()
    pegawai = PegawaiService(session).create(
        nip="123456789012345678", nama_lengkap="A", status_pegawai="nonaktif",
        email_dinas="  A@EXAMPLE.COM ")
    PegawaiService(session).deactivate(pegawai, "pensiun")
    assert pegawai.email_dinas_normalized == "a@example.com"
    assert not pegawai.is_active and pegawai.status_pegawai == "pensiun"
    assert pegawai.deleted_at is None


def test_org_service_update_can_reactivate_unit():
    session = FakeSession()
    unit_obj = OrgUnitService(session).create(**{**unit(), "is_active": False})

    OrgUnitService(session).update(unit_obj, is_active=True)

    assert unit_obj.is_active is True


def test_seed_is_idempotent_and_deterministic():
    session = FakeSession()
    summary = OrgUnitSeedService(session).seed([unit()])
    again = OrgUnitSeedService(session).seed([unit()])
    assert summary["inserted"] == 1
    assert again["unchanged"] == 1 and again["inserted"] == 0
    assert len(session.items) == 1


def test_active_pegawai_requires_active_primary_org():
    inactive = SimpleNamespace(is_active=False)
    with pytest.raises(ValueError):
        PegawaiService(FakeSession()).create(
            nip="123456789012345678", nama_lengkap="A", status_pegawai="aktif",
            primary_org_unit=inactive)


def test_org_service_creates_consistent_unit():
    obj = OrgUnitService(FakeSession()).create(**unit())
    assert obj.path == "/kanwil-jabar"
    assert obj.keycloak_group_path == "/pegawai/kanwil-jabar"
    assert obj.is_active is True
    assert obj.deleted_at is None


def test_pegawai_service_rejects_invalid_status():
    with pytest.raises(ValueError, match="status"):
        PegawaiService(FakeSession()).create(
            nip="123456789012345678", nama_lengkap="A", status_pegawai="invalid")


def test_pegawai_update_active_to_nonaktif_keeps_database_invariant():
    org = OrgUnit(is_active=True)
    pegawai = PegawaiService(FakeSession()).create(
        nip="123456789012345678", nama_lengkap="A", status_pegawai="aktif",
        primary_org_unit=org)

    PegawaiService(FakeSession()).update(pegawai, status_pegawai="nonaktif")

    assert pegawai.status_pegawai == "nonaktif"
    assert pegawai.is_active is False


def test_pegawai_update_rejects_identity_field_changes():
    pegawai = PegawaiService(FakeSession()).create(
        nip="123456789012345678", nama_lengkap="A", status_pegawai="nonaktif")

    with pytest.raises(ValueError, match="field pegawai"):
        PegawaiService(FakeSession()).update(pegawai, nip="999999999999999999")
