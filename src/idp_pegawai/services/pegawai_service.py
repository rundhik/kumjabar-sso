from datetime import date

from sqlalchemy.orm import Session

from idp_pegawai.models.pegawai import Pegawai


class PegawaiService:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _email(value):
        return value.strip().lower() if value else None

    def create(self, **data) -> Pegawai:
        org = data.get("primary_org_unit")
        if data.get("status_pegawai") == "aktif" and (org is None or not org.is_active):
            raise ValueError("pegawai aktif wajib memiliki unit utama aktif")
        for field in ("email_dinas", "email_google"):
            data[f"{field}_normalized"] = self._email(data.get(field))
        obj = Pegawai(**data)
        self.session.add(obj)
        return obj

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
