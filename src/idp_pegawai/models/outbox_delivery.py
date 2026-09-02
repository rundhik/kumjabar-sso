from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from .base import ModelBase


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    CLAIMING = "claiming"
    DISPATCHED = "dispatched"
    RETRY_WAIT = "retry_wait"
    BLOCKED = "blocked"
    DEAD_LETTER = "dead_letter"


class OutboxConsumerDelivery(ModelBase):
    __tablename__ = "outbox_consumer_deliveries"
    __table_args__ = (
        UniqueConstraint("outbox_event_id", "consumer_code", name="uq_outbox_consumer_deliveries_event_consumer"),
        Index("uq_outbox_consumer_deliveries_dispatched_job_id", "dispatched_job_id", unique=True, postgresql_where="dispatched_job_id IS NOT NULL"),
    )

    outbox_event_id: Mapped[int] = mapped_column(ForeignKey("outbox_events.id", ondelete="CASCADE"), nullable=False)
    consumer_code: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=DeliveryStatus.PENDING.value)
    dispatch_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_dispatch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(255))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_job_id: Mapped[UUID | None] = mapped_column()
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __init__(self, **kwargs):
        kwargs.setdefault("uuid", uuid4())
        kwargs.setdefault("status", DeliveryStatus.PENDING.value)
        kwargs.setdefault("dispatch_attempt_count", 0)
        kwargs.setdefault("lease_generation", 0)
        super().__init__(**kwargs)


__all__ = ["DeliveryStatus", "OutboxConsumerDelivery"]