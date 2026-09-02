from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from idp_pegawai.models.identity_link import PegawaiIdentityLink


class IdentityLinkConflict(ValueError):
    """Conflict is retained as a blocked record and never auto-resolved."""


def _uuid(value: object, name: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise IdentityLinkConflict(f"{name} harus UUID") from exc


def project_identity_link(session, event: dict) -> PegawaiIdentityLink:
    aggregate_uuid = _uuid(event["aggregate_uuid"], "aggregate_uuid")
    correlation_uuid = _uuid(event["correlation_uuid"], "correlation_uuid")
    version = int(event["source_version"])
    subject = str(_uuid(event["provider_subject"], "provider_subject"))
    existing = session.scalar(select(PegawaiIdentityLink).where(PegawaiIdentityLink.uuid == aggregate_uuid))
    by_subject = session.scalar(select(PegawaiIdentityLink).where(PegawaiIdentityLink.provider_subject == subject))
    if by_subject is not None and (existing is None or by_subject is not existing) and by_subject.link_status != "unlinked":
        by_subject.link_status = "blocked"
        session.flush()
        raise IdentityLinkConflict("provider subject sudah terhubung ke pegawai lain")
    if existing is not None:
        if version <= existing.link_version:
            return existing
        existing.link_version = version
        existing.link_status = event["link_status"]
        existing.correlation_uuid = correlation_uuid
        if existing.link_status == "unlinked":
            from datetime import datetime, timezone
            existing.unlinked_at = datetime.now(timezone.utc)

        session.flush()
        return existing
    from datetime import datetime, timezone
    record = PegawaiIdentityLink(
        id=event.get("id", aggregate_uuid.int % (2**63 - 1)), uuid=aggregate_uuid,
        pegawai_id=event.get("pegawai_id", 0), provider=event["provider"],
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        provider_subject=subject, management_mode=event["management_mode"],
        link_status=event["link_status"], link_version=version, correlation_uuid=correlation_uuid,
    )
    session.add(record)
    session.flush()
    return record