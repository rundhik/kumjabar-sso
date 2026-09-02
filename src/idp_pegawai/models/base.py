from datetime import datetime
from uuid import uuid4

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import BigInteger, DateTime, JSON, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDMixin:
    uuid: Mapped[Uuid] = mapped_column(Uuid(as_uuid=True), unique=True, nullable=False, default=uuid4)


class TimestampMixin:
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, onupdate=datetime.utcnow, nullable=False)


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModelBase(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __abstract__ = True
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, key="metadata_", nullable=False, default=dict)

    def __init__(self, **kwargs):
        if "metadata" in kwargs:
            kwargs["metadata_"] = kwargs.pop("metadata")
        super().__init__(**kwargs)
        if self.metadata_ is None:
            self.metadata_ = {}

    def __getattribute__(self, name):
        if name == "metadata":
            return object.__getattribute__(self, "metadata_")
        return super().__getattribute__(name)

# Kept as an extension-compatible handle for Flask/Alembic users.
db = SQLAlchemy(model_class=Base)

# SQLAlchemy reserves ``metadata`` on declarative classes; expose the database
# column under its schema name as well for Alembic/introspection consumers.
ModelBase.__table__ if hasattr(ModelBase, "__table__") else None

__all__ = ["Base", "ModelBase", "UUIDMixin", "TimestampMixin", "SoftDeleteMixin", "db"]
