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

    def get_by_identity_link(self, provider: str, provider_subject: str) -> Pegawai | None:
        statement = self._base().join(Pegawai.identity_links).where(
            PegawaiIdentityLink.provider == provider,
            PegawaiIdentityLink.provider_subject == provider_subject,
            PegawaiIdentityLink.is_active.is_(True),
            PegawaiIdentityLink.deleted_at.is_(None),
        )
        return self.session.scalar(statement)

    def list_active_snapshot_scope(self) -> list[Pegawai]:
        statement = self._base().where(Pegawai.is_active.is_(True)).options(
            selectinload(Pegawai.primary_org_unit),
            selectinload(Pegawai.identity_links),
        ).order_by(Pegawai.nip)
        return list(self.session.scalars(statement))


__all__ = ["PegawaiRepository"]
