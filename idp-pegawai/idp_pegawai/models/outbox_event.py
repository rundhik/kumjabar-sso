from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import ModelBase


class OutboxEvent(ModelBase):
    """Durable, non-sensitive notification emitted with a domain mutation."""

    __tablename__ = "outbox_events"
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False, default="import_batch")
    aggregate_uuid: Mapped[UUID] = mapped_column(nullable=False)
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now().astimezone())
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")


__all__ = ["OutboxEvent"]
