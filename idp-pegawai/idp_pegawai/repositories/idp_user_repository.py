"""Repository query-only untuk IdpUser — Slice 3."""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.idp_user import IdpUser


class IdpUserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_username(self, username: str) -> IdpUser | None:
        if not username:
            return None
        norm = str(username).strip().lower()
        return (
            self.session.query(IdpUser)
            .filter(func.lower(IdpUser.username) == norm)
            .first()
        )

    def get_by_id(self, user_id: int) -> IdpUser | None:
        return self.session.get(IdpUser, user_id)

    def get_by_email(self, email: str) -> IdpUser | None:
        if not email:
            return None
        norm = str(email).strip().lower()
        return (
            self.session.query(IdpUser)
            .filter(func.lower(IdpUser.email) == norm)
            .first()
        )
