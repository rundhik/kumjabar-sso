from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from idp_pegawai.models.org_unit import OrgUnit


class OrgUnitRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_uuid(self, uuid: UUID) -> OrgUnit | None:
        return self.session.scalar(select(OrgUnit).where(OrgUnit.uuid == uuid, OrgUnit.deleted_at.is_(None)))

    def get_by_code(self, code: str) -> OrgUnit | None:
        return self.session.scalar(select(OrgUnit).where(OrgUnit.code == code, OrgUnit.deleted_at.is_(None)))

    def get_by_path(self, path: str) -> OrgUnit | None:
        return self.session.scalar(select(OrgUnit).where(OrgUnit.path == path, OrgUnit.deleted_at.is_(None)))

    def list_children(self, parent_uuid: UUID) -> list[OrgUnit]:
        statement = (
            select(OrgUnit)
            .where(OrgUnit.parent.has(uuid=parent_uuid), OrgUnit.deleted_at.is_(None))
            .order_by(OrgUnit.sort_order, OrgUnit.name)
        )
        return list(self.session.scalars(statement))

    def list_active(self) -> list[OrgUnit]:
        # Admin master data must retain visibility of inactive units.
        statement = select(OrgUnit).where(OrgUnit.deleted_at.is_(None)).order_by(OrgUnit.level, OrgUnit.sort_order, OrgUnit.name)
        return list(self.session.scalars(statement))


__all__ = ["OrgUnitRepository"]
