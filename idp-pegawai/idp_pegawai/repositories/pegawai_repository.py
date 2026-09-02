from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from idp_pegawai.models.identity_link import PegawaiIdentityLink
from idp_pegawai.models.pegawai import Pegawai


class PegawaiRepository:
    def __init__(self, session: Session):
        self.session = session

    def _base(self):
        return select(Pegawai).where(Pegawai.deleted_at.is_(None))

    def get_by_uuid(self, uuid: UUID) -> Pegawai | None:
        return self.session.scalar(self._base().where(Pegawai.uuid == uuid))

    def get_by_nip(self, nip: str) -> Pegawai | None:
        return self.session.scalar(self._base().where(Pegawai.nip == nip))

    def get_by_identity_link(self, provider: str, provider_subject: str, issuer: str | None = None) -> Pegawai | None:
        statement = self._base().join(Pegawai.identity_links).where(
            PegawaiIdentityLink.provider == provider,
            PegawaiIdentityLink.provider_subject == provider_subject,
            PegawaiIdentityLink.is_active.is_(True),
        )
        if issuer is not None:
            statement = statement.where(PegawaiIdentityLink.issuer == issuer)
        return self.session.scalar(statement)

    def get_by_keycloak_user_id(self, keycloak_user_id: str) -> Pegawai | None:
        """Fallback lookup by legacy keycloak_user_id column."""
        if not keycloak_user_id:
            return None
        return self.session.scalar(
            self._base().where(Pegawai.keycloak_user_id == keycloak_user_id)
        )

    def list_active_snapshot_scope(self) -> list[Pegawai]:
        """Return every non-deleted employee for the admin master-data list.

        The historical method name is kept for compatibility with existing
        wiring, but the UI must show inactive and other lifecycle statuses too.
        """
        statement = self._base().options(
            selectinload(Pegawai.primary_org_unit),
        ).order_by(Pegawai.nip)
        return list(self.session.scalars(statement))

    def list_status_counts(self) -> dict[str, int]:
        records = self.list_active_snapshot_scope()
        counts = {"aktif": 0, "nonaktif": 0, "mutasi_keluar": 0, "pensiun": 0, "meninggal": 0}
        for record in records:
            counts[record.status_pegawai] = counts.get(record.status_pegawai, 0) + 1
        return counts


__all__ = ["PegawaiRepository"]
