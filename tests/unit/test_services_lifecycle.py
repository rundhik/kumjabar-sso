from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from idp_pegawai.models import Base, OrgUnit, Pegawai
from idp_pegawai.services import OrgUnitSeedService, OrgUnitService, PegawaiService


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    OrgUnit.__table__.create(engine)
    with Session(engine) as s:
        yield s


def unit(code="KANWIL_JABAR", slug="kanwil-jabar", name="Kanwil Jawa Barat"):
    return dict(code=code, slug=slug, name=name, unit_type="kanwil", level=0,
                path=f"/{slug}", keycloak_group_path=f"/pegawai/{slug}")


def test_org_service_rejects_inconsistent_paths(session):
    service = OrgUnitService(session)
    with pytest.raises(ValueError, match="path"):
        service.create(**{**unit(), "path": "/wrong"})


def test_pegawai_service_normalizes_email_and_deactivates_without_delete(session):
    org = OrgUnit(**unit()); session.add(org); session.flush()
    service = PegawaiService(session)
    pegawai = service.create(nip="123456789012345678", nama_lengkap="A", status_pegawai="aktif",
                              primary_org_unit=org, email_dinas="  A@EXAMPLE.COM ")
    service.deactivate(pegawai, "pensiun")
    assert pegawai.email_dinas_normalized == "a@example.com"
    assert not pegawai.is_active and pegawai.status_pegawai == "pensiun"
    assert pegawai.deleted_at is None


def test_seed_is_idempotent_and_deterministic(session):
    summary = OrgUnitSeedService(session).seed([unit()])
    again = OrgUnitSeedService(session).seed([unit()])
    assert summary["inserted"] == 1
    assert again["unchanged"] == 1 and again["inserted"] == 0
    assert session.query(OrgUnit).count() == 1


def test_active_pegawai_requires_active_primary_org(session):
    inactive = OrgUnit(**{**unit(), "is_active": False}); session.add(inactive); session.flush()
    with pytest.raises(ValueError):
        PegawaiService(session).create(nip="123456789012345678", nama_lengkap="A", status_pegawai="aktif",
                                       primary_org_unit=inactive)
