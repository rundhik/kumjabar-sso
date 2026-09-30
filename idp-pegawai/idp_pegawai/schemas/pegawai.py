from typing import Any


def serialize_pegawai(pegawai: Any) -> dict:
    unit = getattr(pegawai, "primary_org_unit", None)
    return {
        "uuid": str(pegawai.uuid),
        "nip": pegawai.nip,
        "nama_lengkap": pegawai.nama_lengkap,
        "gelar_depan": pegawai.gelar_depan,
        "gelar_belakang": pegawai.gelar_belakang,
        "status_pegawai": pegawai.status_pegawai,
        "is_active": pegawai.is_active,
        "primary_org_unit": None if unit is None else {
            "uuid": str(unit.uuid),
            "code": unit.code,
            "name": unit.name,
        },
    }


__all__ = ["serialize_pegawai"]

