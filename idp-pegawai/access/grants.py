"""Value object for the thin, explicitly scoped local access grant."""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .catalog import CRITICAL_ROLES, Role, ScopeType


class GrantStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass(frozen=True)
class AccessGrant:
    role: Role
    scope_type: ScopeType
    scope_root_id: int | None = None
    valid_until: datetime | None = None
    status: GrantStatus = GrantStatus.ACTIVE

    def __post_init__(self) -> None:
        if self.scope_type is ScopeType.ORG_UNIT_SUBTREE and self.scope_root_id is None:
            raise ValueError("org_unit_subtree grant requires scope_root_id")
        if self.scope_type is ScopeType.GLOBAL and self.scope_root_id is not None:
            raise ValueError("global grant cannot have scope_root_id")
        if self.role in CRITICAL_ROLES and self.valid_until is None:
            raise ValueError("critical grant requires valid_until")
        if self.status is not GrantStatus.ACTIVE:
            raise ValueError("new grants must be active")

    @property
    def is_effective(self) -> bool:
        return self.status is GrantStatus.ACTIVE and (
            self.valid_until is None or self.valid_until > datetime.now(timezone.utc)
        )
