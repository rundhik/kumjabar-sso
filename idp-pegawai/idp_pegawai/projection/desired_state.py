from dataclasses import dataclass
from typing import Any
from uuid import UUID

from .mapping_catalog import ATTRIBUTE_CATALOG, CLIENT_ROLE_CATALOG, GROUP_PREFIX, REALM_ROLE_CATALOG


class ProjectionContractError(ValueError):
    pass


@dataclass(frozen=True)
class DesiredState:
    contract_version: str
    aggregate_type: str
    aggregate_uuid: str
    source_version: int
    identity: dict[str, Any]
    account: dict[str, bool]
    managed_attributes: dict[str, list[str]]
    managed_groups: list[dict[str, str]]
    managed_realm_roles: list[str]
    managed_client_roles: dict[str, list[str]]

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


class DesiredStateResolver:
    def resolve(self, pegawai: Any, *, remote_group_path=None, role=None, claims=None) -> DesiredState:
        if remote_group_path is not None or role is not None or claims is not None:
            raise ProjectionContractError("remote mapping/claims harus berasal dari katalog")
        uid = str(pegawai.uuid).lower()
        try:
            UUID(uid)
        except ValueError as exc:
            raise ProjectionContractError("pegawai.uuid invalid") from exc
        active = bool(pegawai.is_active) and pegawai.status_pegawai == "aktif"
        org = getattr(pegawai, "primary_org_unit", None)
        if active and (org is None or not getattr(org, "is_active", False)):
            raise ProjectionContractError("pegawai aktif wajib memiliki canonical org unit")
        version = int(getattr(pegawai, "source_version", None) or getattr(pegawai, "metadata_", {}).get("source_version", 1))
        attrs = {"idp_pegawai_uuid": [uid], "idp_source_version": [str(version)], "user_type": ["pegawai"], "pegawai_status": [pegawai.status_pegawai]}
        groups = []
        if active:
            path = org.keycloak_group_path
            if not path.startswith(GROUP_PREFIX + "/"):
                raise ProjectionContractError("group path bukan canonical managed path")
            attrs.update(primary_org_unit_code=[org.code], primary_org_unit_path=[org.path], org_unit_codes=[org.code], org_group_paths=[path])
            groups = [{"org_unit_uuid": str(org.uuid).lower(), "code": org.code, "path": path, "membership_kind": "primary"}]
        return DesiredState("keycloak-projection.v1", "pegawai", uid, version,
            {"identity_link_uuid": "", "keycloak_user_id": "", "management_mode": "idp_managed"},
            {"enabled": active}, attrs, groups, ["pegawai"] if active else [], dict(CLIENT_ROLE_CATALOG))

__all__ = ["DesiredState", "DesiredStateResolver", "ProjectionContractError"]

assert set(("idp_pegawai_uuid", "idp_source_version", "user_type", "pegawai_status", "primary_org_unit_code", "primary_org_unit_path", "org_unit_codes", "org_group_paths")) == ATTRIBUTE_CATALOG
assert REALM_ROLE_CATALOG == frozenset({"pegawai"})
