"""IdpUser model — buku daftar satpam (Dok 37 §4.2-4.3)."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, validates

from werkzeug.security import check_password_hash, generate_password_hash

from .base import ModelBase

_USERNAME_RE = re.compile(r"^[a-z0-9._-]+$")


class IdpUser(ModelBase):
    __tablename__ = "idp_users"
    __table_args__ = (
        CheckConstraint("role IN ('admin','operator')", name="ck_idp_users_role_allowed"),
        CheckConstraint("failed_attempts >= 0", name="ck_idp_users_failed_attempts_non_negative"),
    )

    # override id? ModelBase already BigInteger PK, keep it
    username: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="operator")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @validates("username")
    def validate_username(self, key, value):
        if value is None:
            raise ValueError("username wajib diisi")
        v = str(value).strip().lower()
        if not (3 <= len(v) <= 80):
            raise ValueError("username harus 3-80 karakter")
        if not _USERNAME_RE.fullmatch(v):
            raise ValueError("username hanya boleh huruf kecil, angka, titik, underscore, atau dash")
        return v

    @validates("email")
    def validate_email(self, key, value):
        if value is None or str(value).strip() == "":
            return None
        v = str(value).strip().lower()
        if len(v) > 255:
            raise ValueError("email maksimal 255 karakter")
        # simple validation; email-validator available but keep light for model
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("format email tidak valid")
        return v

    @validates("role")
    def validate_role(self, key, value):
        v = str(value).strip().lower() if value is not None else "operator"
        if v not in ("admin", "operator"):
            raise ValueError("role harus admin atau operator")
        return v

    def __init__(self, **kwargs):
        # normalize username/email/role before super
        if "username" in kwargs and kwargs["username"] is not None:
            kwargs["username"] = str(kwargs["username"]).strip().lower()
        if "email" in kwargs:
            val = kwargs["email"]
            if val is None or str(val).strip() == "":
                kwargs["email"] = None
            else:
                kwargs["email"] = str(val).strip().lower()
        if "role" in kwargs and kwargs["role"] is not None:
            kwargs["role"] = str(kwargs["role"]).strip().lower()
        super().__init__(**kwargs)
        # ensure username lower already, but double-check after init for direct assignment
        if hasattr(self, "username") and self.username:
            self.username = self.username.strip().lower()
        if hasattr(self, "email") and self.email:
            self.email = self.email.strip().lower() if self.email else None
        # validate role
        if self.role not in ("admin", "operator"):
            raise ValueError("role harus admin atau operator")
        # ensure failed_attempts non-negative
        if self.failed_attempts is None:
            self.failed_attempts = 0

    # --- password helpers ---

    def set_password(self, password: str) -> None:
        """Hash dan simpan password. Validasi diserahkan ke caller (validator)."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        try:
            return check_password_hash(self.password_hash, password)
        except Exception:
            return False

    @property
    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        now = datetime.now(timezone.utc)
        lu = self.locked_until
        if lu.tzinfo is None:
            lu = lu.replace(tzinfo=timezone.utc)
        return lu > now


__all__ = ["IdpUser"]
