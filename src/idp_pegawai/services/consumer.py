from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from idp_pegawai.models.consumer import ConsumerChangeLog, ConsumerRegistration


class ConsumerService:
    def __init__(self, session):
        self.session = session

    def register(self, consumer_code, **values):
        existing = self.session.scalar(select(ConsumerRegistration).where(ConsumerRegistration.consumer_code == consumer_code))
        if existing:
            if existing.status in {"revoked", "decommissioned"}:
                raise ValueError("consumer_code is permanently reserved")
            if values.get("service_client_id") != existing.service_client_id:
                raise ValueError("consumer binding cannot change")
            return existing
        bound = self.session.scalar(select(ConsumerRegistration).where(ConsumerRegistration.service_client_id == values["service_client_id"]))
        if bound:
            raise ValueError("service client is already actively bound")
        row = ConsumerRegistration(consumer_code=consumer_code, consumer_name=values["name"], **{k: v for k, v in values.items() if k != "name"})
        self.session.add(row)
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise ValueError("consumer binding conflict") from exc
        return row

    def publish(self, resource_uuid: UUID, resource_type, source_version, payload, field_profile, contract_version, action="upsert"):
        if action not in {"upsert", "tombstone"} or (action == "upsert") != (payload is not None):
            raise ValueError("upsert requires payload; tombstone forbids payload")
        canonical = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"))
        last = self.session.scalar(select(ConsumerChangeLog).order_by(ConsumerChangeLog.change_sequence.desc()))
        row = ConsumerChangeLog(change_sequence=(last.change_sequence + 1 if last else 1), resource_uuid=resource_uuid, resource_type=resource_type, change_type=action, source_version=source_version, contract_version=contract_version, field_profile=field_profile, payload_hash=hashlib.sha256(canonical.encode()).hexdigest(), payload=payload)
        self.session.add(row)
        self.session.flush()
        return row


__all__ = ["ConsumerService"]

