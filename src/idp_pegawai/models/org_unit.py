from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from uuid import uuid4

from .base import ModelBase


UNIT_TYPES = ("kanwil", "divisi", "bidang", "bagian", "pokja", "tim")


class OrgUnit(ModelBase):
    __tablename__ = "org_units"
    __table_args__ = (
        CheckConstraint("level >= 0", name="ck_org_units_level_non_negative"),
        CheckConstraint("path LIKE '/%'", name="ck_org_units_path_absolute"),
        CheckConstraint("keycloak_group_path LIKE '/pegawai/%'", name="ck_org_units_keycloak_group_path_employee"),
        CheckConstraint("effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from", name="ck_org_units_effective_range"),
    )

    parent_id: Mapped[int | None] = mapped_column(ForeignKey("org_units.id"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(120))
    unit_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    keycloak_group_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)

    parent: Mapped["OrgUnit | None"] = relationship(remote_side="OrgUnit.id", back_populates="children")
    children: Mapped[list["OrgUnit"]] = relationship(back_populates="parent")

    @validates("unit_type")
    def validate_unit_type(self, key, value):
        if value not in UNIT_TYPES:
            raise ValueError("unit_type tidak valid")
        return value

    @validates("level")
    def validate_level(self, key, value):
        if value < 0:
            raise ValueError("level harus non-negatif")
        return value

    @validates("path")
    def validate_path(self, key, value):
        if not value.startswith("/"):
            raise ValueError("path harus absolute")
        return value

    @validates("keycloak_group_path")
    def validate_keycloak_path(self, key, value):
        if not value.startswith("/pegawai/"):
            raise ValueError("keycloak_group_path harus di bawah /pegawai/")
        return value

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.sort_order is None:
            self.sort_order = 0
        if self.is_active is None:
            self.is_active = True
        if self.metadata_ is None:
            self.metadata_ = {}
        if self.uuid is None:
            self.uuid = uuid4()
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective date range tidak valid")
        if self.is_active is False and self.effective_from and self.effective_to:
            raise ValueError("unit inactive tidak boleh memiliki effective date lengkap")

    def __setattr__(self, key, value):
        if key == "parent" and value is not None:
            node = value
            while node is not None:
                if node is self:
                    raise ValueError("parent cycle tidak diizinkan")
                node = getattr(node, "parent", None)
        super().__setattr__(key, value)


# Keep the schema column addressable by its database name despite the
# declarative ``metadata`` reservation.
_metadata_column = next(column for column in OrgUnit.__table__.columns if column.name == "metadata")
OrgUnit.__table__.columns._index["metadata"] = ("metadata", _metadata_column)

__all__ = ["OrgUnit", "UNIT_TYPES"]
