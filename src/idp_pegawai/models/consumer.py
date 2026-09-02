from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import ModelBase


class ConsumerRegistration(ModelBase):
    __tablename__ = "consumer_registrations"
    __table_args__ = (
        UniqueConstraint("consumer_code", name="uq_consumer_registrations_code"),
        UniqueConstraint("service_client_id", name="uq_consumer_registrations_client"),
    )

    consumer_code: Mapped[str] = mapped_column(String(80), nullable=False)
    consumer_name: Mapped[str] = mapped_column(String(150), nullable=False)
    owner_unit: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    service_client_id: Mapped[str] = mapped_column(String(120), nullable=False)
    allowed_resource_families: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    allowed_field_profile: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="proposed")
    max_page_size: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    replay_window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ConsumerChangeLog(ModelBase):
    __tablename__ = "consumer_change_log"
    # The inherited ModelBase id is replaced: sequence is the feed's sole key.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=False, nullable=True)
    __table_args__ = (
        CheckConstraint("change_type IN ('upsert', 'tombstone')", name="ck_consumer_change_log_type"),
        CheckConstraint("(change_type = 'upsert' AND payload IS NOT NULL) OR (change_type = 'tombstone' AND payload IS NULL)", name="ck_consumer_change_log_action_payload"),
    )

    change_sequence: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_uuid: Mapped[UUID] = mapped_column(nullable=False)
    change_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contract_version: Mapped[str] = mapped_column(String(80), nullable=False)
    field_profile: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_outbox_event_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    @property
    def source_version_order(self):
        return self.change_sequence
