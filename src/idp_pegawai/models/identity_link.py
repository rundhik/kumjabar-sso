from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .base import Base, UUIDMixin, TimestampMixin

PROVIDERS = ("keycloak", "google", "microsoft", "local")


class PegawaiIdentityLink(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pegawai_identity_links"
    __table_args__ = (
        CheckConstraint("provider IN ('keycloak','google','microsoft','local')", name="ck_pegawai_identity_links_provider_allowed"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pegawai_id: Mapped[int] = mapped_column(ForeignKey("pegawai.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(255))
    email_normalized: Mapped[str | None] = mapped_column(String(255), index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    linked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, key="metadata_", nullable=False, default=dict)
    management_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="idp_managed")
    link_status: Mapped[str] = mapped_column(String(30), nullable=False, default="reserved")
    link_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    correlation_uuid: Mapped[object | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pegawai = relationship("Pegawai", back_populates="identity_links")

    @validates("provider")
    def validate_provider(self, key, value):
        if value not in PROVIDERS:
            raise ValueError("provider tidak valid")
        return value

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.provider not in PROVIDERS:
            raise ValueError("provider tidak valid")
        if not self.provider_subject:
            raise ValueError("provider_subject wajib diisi")


__all__ = ["PegawaiIdentityLink", "PROVIDERS"]

_metadata_column = next(column for column in PegawaiIdentityLink.__table__.columns if column.name == "metadata")
PegawaiIdentityLink.__table__.columns._index["metadata"] = ("metadata", _metadata_column)
PegawaiIdentityLink.__table__.columns._index["metadata_"] = ("metadata_", _metadata_column)