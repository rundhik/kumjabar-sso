import pytest
from sqlalchemy import inspect

from idp_pegawai.models import Pegawai, PegawaiIdentityLink


def pegawai(**kwargs):
    values = dict(nip="123456789012345678", nama_lengkap="Siti", status_pegawai="aktif", is_active=True)
    values.update(kwargs)
    return Pegawai(**values)


def test_pegawai_has_contract_fields_and_primary_org_relationship():
    columns = {c.name for c in inspect(Pegawai).columns}
    assert {"nip", "nama_lengkap", "gelar_depan", "gelar_belakang", "email_dinas", "email_dinas_normalized", "email_google", "email_google_normalized", "no_hp", "primary_org_unit_id", "status_pegawai", "is_active", "status_reason", "status_effective_at", "keycloak_user_id", "metadata", "deleted_at"} <= columns
    assert hasattr(Pegawai, "primary_org_unit")
    assert not {"jabatan", "jabatan_type", "plt", "plh"} & columns


@pytest.mark.parametrize("nip", ["123", "12345678901234567X", "１２３４５６７８９０１２３４５６７８"])
def test_nip_is_exactly_18_ascii_digits(nip):
    with pytest.raises(ValueError):
        pegawai(nip=nip)


def test_active_pegawai_requires_primary_unit_and_status_controls_eligibility():
    with pytest.raises(ValueError):
        pegawai()
    assert pegawai(status_pegawai="pensiun", is_active=False).is_active is False
    with pytest.raises(ValueError):
        pegawai(status_pegawai="pensiun", is_active=True)


def test_identity_link_contract_and_provider_subject_uniqueness():
    columns = {c.name for c in inspect(PegawaiIdentityLink).columns}
    assert {"pegawai_id", "provider", "provider_subject", "email", "email_normalized", "email_verified", "is_active", "linked_at", "last_seen_at", "metadata"} <= columns
    assert PegawaiIdentityLink.__table__.c.provider_subject.unique
    link = PegawaiIdentityLink(provider="google", provider_subject="sub-1")
    assert link.pegawai is None
    assert not hasattr(PegawaiIdentityLink, "deleted_at")


def test_provider_must_be_supported_and_subject_required():
    with pytest.raises(ValueError):
        PegawaiIdentityLink(provider="unknown", provider_subject="x")
    with pytest.raises(ValueError):
        PegawaiIdentityLink(provider="google")
