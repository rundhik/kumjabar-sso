from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import ModelBase


STATUSES = ("received", "quarantined", "rejected", "registered", "mapped", "staging", "staged", "validating", "validated", "ready_to_apply", "applying", "applied", "stale", "failed", "cancelled")


class ImportBatch(ModelBase):
    __tablename__ = "import_batches"
    parent_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"))
    root_batch_uuid: Mapped[UUID] = mapped_column(nullable=False)
    retry_reason: Mapped[str | None] = mapped_column(String(80))
    retry_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    import_type: Mapped[str] = mapped_column(String(40), nullable=False, default="pegawai")
    input_profile: Mapped[str] = mapped_column(String(60), nullable=False, default="pegawai_standard_v1")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="received")
    source_format: Mapped[str] = mapped_column(String(10), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(255), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mapping_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.uuid is None:
            self.uuid = uuid4()
        if self.root_batch_uuid is None:
            self.root_batch_uuid = self.uuid
        if self.received_at is None:
            self.received_at = datetime.now().astimezone()
        if self.created_at is None:
            self.created_at = datetime.now().astimezone()
        if self.updated_at is None:
            self.updated_at = self.created_at
        if self.status is None:
            self.status = "received"

__all__ = ["ImportBatch", "STATUSES"]
