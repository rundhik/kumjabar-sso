from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.orm import Session

from idp_pegawai.models.org_unit import OrgUnit


class OrgUnitService:
    def __init__(self, session: Session):
        self.session = session

    def create(self, **data) -> OrgUnit:
        slug = data["slug"]
        expected_path = f"/{slug}" if data.get("parent") is None else f'{data["parent"].path}/{slug}'
        if data.get("path") != expected_path:
            raise ValueError("path tidak konsisten dengan parent dan slug")
        if data.get("keycloak_group_path") != f"/pegawai{expected_path}":
            raise ValueError("keycloak_group_path tidak konsisten")
        obj = OrgUnit(**data)
        self.session.add(obj)
        return obj


class OrgUnitSeedService:
    def __init__(self, session: Session):
        self.session = session

    def seed(self, rows: list[dict]) -> dict[str, int | list]:
        result = {"seed_name": "org_units.v1", "total_rows": len(rows), "inserted": 0, "updated": 0, "unchanged": 0, "errors": []}
        for row in rows:
            existing = self.session.query(OrgUnit).filter_by(code=row["code"], deleted_at=None).one_or_none()
            expected = dict(row)
            expected["uuid"] = uuid5(NAMESPACE_URL, f"kumjabar-sso/org-unit/{row['code']}")
            if existing is None:
                self.session.add(OrgUnit(**expected)); result["inserted"] += 1
            else:
                changed = False
                for key, value in row.items():
                    if key not in {"code", "uuid", "parent_code"} and getattr(existing, key, None) != value:
                        setattr(existing, key, value); changed = True
                result["updated" if changed else "unchanged"] += 1
        self.session.flush()
        return result


__all__ = ["OrgUnitService", "OrgUnitSeedService"]

# seed contract entry point retained for CLI integration in a later slice
seed_org_units = OrgUnitSeedService.seed
