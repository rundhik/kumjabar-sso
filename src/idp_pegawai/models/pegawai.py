from datetime import date
import re

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .base import ModelBase


STATUSES = ("aktif", "mutasi_keluar", "pensiun", "nonaktif", "meninggal")


class Pegawai(ModelBase):
    __tablename__ = "pegawai"
    __table_args__ = (
        CheckConstraint("nip ~ '^[0-9]{18}$'", name="ck_pegawai_nip_18_digits"),
        CheckConstraint("status_pegawai IN ('aktif','mutasi_keluar','pensiun','nonaktif','meninggal')", name="ck_pegawai_status_allowed"),
        CheckConstraint("is_active = (status_pegawai = 'aktif')", name="ck_pegawai_active_status_consistency"),
        CheckConstraint("is_active = false OR primary_org_unit_id IS NOT NULL", name="ck_pegawai_active_requires_primary_org_unit"),
    )

    nip: Mapped[str] = mapped_column(String(18), nullable=False, index=True)
    nama_lengkap: Mapped[str] = mapped_column(String(255), nullable=False)
    gelar_depan: Mapped[str | None] = mapped_column(String(80))
    gelar_belakang: Mapped[str | None] = mapped_column(String(120))
    email_dinas: Mapped[str | None] = mapped_column(String(255))
    email_dinas_normalized: Mapped[str | None] = mapped_column(String(255), index=True)
    email_google: Mapped[str | None] = mapped_column(String(255))
    email_google_normalized: Mapped[str | None] = mapped_column(String(255), index=True)
    no_hp: Mapped[str | None] = mapped_column(String(50))
    primary_org_unit_id: Mapped[int | None] = mapped_column(ForeignKey("org_units.id"), index=True)
    status_pegawai: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status_reason: Mapped[str | None] = mapped_column(Text)
    status_effective_at: Mapped[date | None] = mapped_column(Date)
    keycloak_user_id: Mapped[str | None] = mapped_column(String(120), index=True)

    primary_org_unit = relationship("OrgUnit", back_populates="primary_pegawai")
    identity_links = relationship("PegawaiIdentityLink", back_populates="pegawai")

    @validates("nip")
    def validate_nip(self, key, value):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{18}", value, flags=re.ASCII):
            raise ValueError("NIP harus tepat 18 digit ASCII")
        return value

    @validates("status_pegawai")
    def validate_status(self, key, value):
        if value not in STATUSES:
            raise ValueError("status pegawai tidak valid")
        return value

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.status_pegawai not in STATUSES:
            raise ValueError("status pegawai tidak valid")
        if self.is_active is None:
            self.is_active = self.status_pegawai == "aktif"
        if self.is_active != (self.status_pegawai == "aktif"):
            raise ValueError("is_active harus konsisten dengan status pegawai")
        if self.is_active and self.primary_org_unit_id is None and getattr(self, "primary_org_unit", None) is None:
            raise ValueError("pegawai aktif wajib memiliki unit utama")


__all__ = ["Pegawai", "STATUSES"]
