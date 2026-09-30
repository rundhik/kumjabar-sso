from datetime import date

from sqlalchemy.orm import Session

from idp_pegawai.models.pegawai import Pegawai, STATUSES


class PegawaiService:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _email(value):
        return value.strip().lower() if value else None

    def create(self, **data) -> Pegawai:
        allowed = {"nip", "nama_lengkap", "gelar_depan", "gelar_belakang", "email_dinas", "email_google", "no_hp", "status_pegawai", "is_active", "primary_org_unit"}
        if set(data) - allowed:
            raise ValueError("field pegawai tidak diizinkan")
        org = data.get("primary_org_unit")
        if data.get("status_pegawai") == "aktif" and (org is None or not org.is_active):
            raise ValueError("pegawai aktif wajib memiliki unit utama aktif")
        for field in ("email_dinas", "email_google"):
            data[f"{field}_normalized"] = self._email(data.get(field))
        obj = Pegawai(**data)
        self.session.add(obj)
        return obj

    def update(self, pegawai: Pegawai, **data) -> Pegawai:
        allowed = {"nama_lengkap", "gelar_depan", "gelar_belakang", "email_dinas", "email_google", "no_hp", "status_pegawai", "is_active", "primary_org_unit"}
        if set(data) - allowed:
            raise ValueError("field pegawai tidak diizinkan")
        if "status_pegawai" in data and data["status_pegawai"] not in STATUSES:
            raise ValueError("status pegawai tidak valid")
        for field in ("email_dinas", "email_google"):
            if field in data:
                setattr(pegawai, field, data[field])
                setattr(pegawai, f"{field}_normalized", self._email(data[field]))
        for key, value in data.items():
            if key not in {"email_dinas", "email_google"}:
                setattr(pegawai, key, value)
        if pegawai.status_pegawai == "aktif":
            if not pegawai.primary_org_unit or not pegawai.primary_org_unit.is_active:
                raise ValueError("pegawai aktif wajib memiliki unit utama aktif")
            pegawai.is_active = True
        else:
            pegawai.is_active = False
        return pegawai

    def deactivate(self, pegawai: Pegawai, status: str = "nonaktif", reason: str | None = None) -> Pegawai:
        if status == "aktif":
            raise ValueError("status deaktif diperlukan")
        pegawai.status_pegawai = status
        pegawai.is_active = False
        pegawai.status_reason = reason
        pegawai.status_effective_at = date.today()
        return pegawai

    def assign_primary(self, pegawai: Pegawai, org_unit) -> Pegawai:
        if not org_unit.is_active:
            raise ValueError("unit nonaktif tidak dapat menjadi assignment baru")
        pegawai.primary_org_unit = org_unit
        return pegawai


__all__ = ["PegawaiService"]

assign_primary_org_unit = PegawaiService.assign_primary
add_additional_org_unit = PegawaiService.assign_primary
remove_additional_org_unit = PegawaiService.assign_primary
