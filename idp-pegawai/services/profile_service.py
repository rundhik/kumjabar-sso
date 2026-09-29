from dataclasses import dataclass

from idp_pegawai.repositories.pegawai_repository import PegawaiRepository


@dataclass(frozen=True)
class ProfileResolutionError(Exception):
    code: str
    message: str


class PegawaiProfileService:
    def __init__(self, repository: PegawaiRepository):
        self.repository = repository

    def resolve(self, *, provider: str, issuer: str, subject: str, nip: str | None = None) -> dict:
        if not provider or not issuer or not subject:
            raise ProfileResolutionError("pegawai_identity_not_found", "identitas pegawai tidak ditemukan")

        # 1. Cari via identity link
        pegawai = self.repository.get_by_identity_link(provider, subject, issuer=issuer)

        # 2. Fallback: Jika belum ada link, cari via repository
        if pegawai is None:
            # Opsi A: Cari via keycloak_user_id di repository
            pegawai = self.repository.get_by_keycloak_user_id(subject)

            # Opsi B: Jika Opsi A kosong & ada NIP, coba cari via NIP
            if pegawai is None and nip:
                pegawai = self.repository.get_by_nip(nip)

        if pegawai is None:
            raise ProfileResolutionError("pegawai_identity_not_found", "identitas pegawai tidak ditemukan")

        if not pegawai.is_active or pegawai.status_pegawai != "aktif":
            raise ProfileResolutionError("pegawai_inactive", "pegawai tidak aktif")

        unit = pegawai.primary_org_unit
        return {
            "pegawai_uuid": str(pegawai.uuid),
            "nip": str(pegawai.nip),
            "email": pegawai.email_dinas,
            "nama_lengkap": pegawai.nama_lengkap,
            "status_pegawai": pegawai.status_pegawai,
            "is_active": bool(pegawai.is_active),
            "primary_org_unit": None if unit is None else {
                "uuid": str(unit.uuid), "code": unit.code, "name": unit.name,
            },
        }
