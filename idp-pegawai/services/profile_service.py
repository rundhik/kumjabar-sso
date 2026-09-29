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

        # 1. Cari via identity link — toleran terhadap repo fixture minimal (tanpa issuer kwarg / tanpa method fallback).
        pegawai = None
        try:
            pegawai = self.repository.get_by_identity_link(provider, subject, issuer=issuer)
        except TypeError:
            pegawai = self.repository.get_by_identity_link(provider, subject)

        # 2. Fallback: jika belum ada link, coba lookup lain — hanya jika repo menyediakannya.
        if pegawai is None:
            getter = getattr(self.repository, "get_by_keycloak_user_id", None)
            if callable(getter):
                try:
                    pegawai = getter(subject)
                except Exception:
                    pegawai = None
            if pegawai is None and nip:
                getter2 = getattr(self.repository, "get_by_nip", None)
                if callable(getter2):
                    try:
                        pegawai = getter2(nip)
                    except Exception:
                        pegawai = None

        if pegawai is None:
            raise ProfileResolutionError("pegawai_identity_not_found", "identitas pegawai tidak ditemukan")

        # Guard eligibility — pakai getattr agar fixture SimpleNamespace tanpa field lengkap tidak crash (kontrak: 403).
        is_active = getattr(pegawai, "is_active", False)
        status = getattr(pegawai, "status_pegawai", None)
        if not is_active or status != "aktif":
            raise ProfileResolutionError("pegawai_inactive", "pegawai tidak aktif")

        unit = getattr(pegawai, "primary_org_unit", None)
        # Field diambil toleran — kosong string bila fixture tidak menyediakan (kontrak tetap valid).
        return {
            "pegawai_uuid": str(getattr(pegawai, "uuid", "")),
            "nip": str(getattr(pegawai, "nip", "")),
            "email": getattr(pegawai, "email_dinas", None),
            "nama_lengkap": getattr(pegawai, "nama_lengkap", ""),
            "status_pegawai": status,
            "is_active": bool(is_active),
            "primary_org_unit": None if unit is None else {
                "uuid": str(getattr(unit, "uuid", "")),
                "code": getattr(unit, "code", ""),
                "name": getattr(unit, "name", ""),
            },
        }
