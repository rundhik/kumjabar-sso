from datetime import datetime, timezone
from uuid import uuid4

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import BigInteger, DateTime, JSON, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator
from uuid import UUID


class FlexibleUUID(TypeDecorator):
    """Keep UUID objects in Python while accepting canonical string filters."""
    impl = Uuid
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or isinstance(value, UUID):
            return value
        return UUID(str(value))

    def process_result_value(self, value, dialect):
        return value


class Base(DeclarativeBase):
    pass


class UUIDMixin:
    uuid: Mapped[UUID] = mapped_column(FlexibleUUID(as_uuid=True), unique=True, nullable=False, default=uuid4)


class TimestampMixin:
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


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
# Deduplicate SQLAlchemy instance across flat-loader aliases (app vs idp_pegawai).
# Without this, ``app.models.base`` and ``idp_pegawai.models.base`` each create
# their own ``SQLAlchemy(Base)`` leading to ``RuntimeError: multiple instances``.
import sys as _sys
_existing = None
for _k in ("idp_pegawai.models.base", "app.models.base", "app.idp_pegawai.models.base"):
    _m = _sys.modules.get(_k)
    if _m is not None and hasattr(_m, "db") and _m is not _sys.modules.get(__name__):
        _existing = _m.db
        break
if _existing is not None:
    db = _existing
else:
    db = SQLAlchemy(model_class=Base)

# SQLAlchemy reserves ``metadata`` on declarative classes; expose the database
# column under its schema name as well for Alembic/introspection consumers.
ModelBase.__table__ if hasattr(ModelBase, "__table__") else None

__all__ = ["Base", "ModelBase", "UUIDMixin", "TimestampMixin", "SoftDeleteMixin", "db"]
