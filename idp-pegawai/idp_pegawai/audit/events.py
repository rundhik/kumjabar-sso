from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from .redaction import bounded_summary, validate_metadata

ACTOR_TYPES = {"pegawai", "service_account", "system"}
OUTCOMES = {"success", "denied", "failed", "conflict"}
SEVERITIES = {"info", "warning", "critical"}
MAX_CHANGED_FIELDS = 100


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    outcome: str
    severity: str
    actor_type: str
    actor_subject: str
    resource_type: str
    event_version: int = 1
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actor_pegawai_uuid: UUID | None = None
    actor_scope_type: str | None = None
    actor_scope_org_unit_uuid: UUID | None = None
    resource_uuid: UUID | None = None
    scope_org_unit_uuid: UUID | None = None
    scope_footprint: tuple[UUID, ...] = ()
    changed_fields: tuple[str, ...] = ()
    change_summary: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_event(**kwargs: Any) -> AuditEvent:
    if kwargs.get("actor_type") not in ACTOR_TYPES or kwargs.get("outcome") not in OUTCOMES or kwargs.get("severity") not in SEVERITIES:
        raise ValueError("aktor, outcome, atau severity tidak valid")
    fields = tuple(sorted(set(kwargs.pop("changed_fields", ()))))
    if len(fields) > MAX_CHANGED_FIELDS or any(not isinstance(x, str) or not x for x in fields):
        raise ValueError("changed_fields tidak valid atau terlalu banyak")
    kwargs["changed_fields"] = fields
    kwargs["scope_footprint"] = tuple(sorted(set(kwargs.pop("scope_footprint", ()) ), key=str))
    kwargs["change_summary"] = bounded_summary(kwargs.get("change_summary"))
    kwargs["metadata"] = validate_metadata(kwargs.get("event_type", ""), kwargs.get("metadata"))
    return AuditEvent(**kwargs)
