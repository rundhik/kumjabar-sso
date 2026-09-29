"""Core in-memory delta feed service; transport-neutral by design."""
from dataclasses import dataclass
from typing import Iterable

from .cursor import CursorError, CursorSigner


class FeedError(ValueError):
    """Invalid curated feed data or request."""


class PageLimitError(FeedError):
    pass


class ReplayExpiredError(CursorError):
    """Cursor is outside the replay window/retention boundary."""


@dataclass(frozen=True)
class FeedPage:
    items: list[dict]
    next_cursor: str | None


class DeltaFeedService:
    HARD_CAP = 500
    _FIELDS = ("change_sequence", "resource_type", "resource_uuid", "change_type",
               "source_version", "contract_version", "field_profile", "payload_hash", "payload")

    def __init__(self, *, signer: CursorSigner, records: Iterable[object]):
        self.signer = signer
        self.records = records if hasattr(records, "__getitem__") else list(records)

    def read(self, *, registration, resource_family: str, limit: int, cursor: str | None = None) -> FeedPage:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= self.HARD_CAP:
            raise PageLimitError("page limit invalid")
        max_page = getattr(registration, "max_page_size", 100)
        if not isinstance(max_page, int) or not 1 <= max_page <= self.HARD_CAP or limit > max_page:
            raise PageLimitError("page limit invalid")
        profile = registration.allowed_field_profile
        contract = "consumer-change.v1"
        position = 0
        if cursor is not None:
            claims = self.signer.decode(cursor, consumer_code=registration.consumer_code,
                registration_uuid=str(registration.uuid), resource_family=resource_family,
                field_profile=profile, contract_version=contract)
            position = claims["position"]
        rows = sorted((r for r in self.records if r.change_sequence > position), key=lambda r: r.change_sequence)
        selected = rows[:limit]
        items = [self._item(row) for row in selected]
        next_cursor = None
        if selected:
            next_cursor = self.signer.encode(consumer_code=registration.consumer_code,
                registration_uuid=str(registration.uuid), resource_family=resource_family,
                field_profile=profile, contract_version=contract, position=selected[-1].change_sequence)
        return FeedPage(items, next_cursor)

    @classmethod
    def _item(cls, row):
        payload = row.payload
        if payload is not None and cls._contains_pii(payload):
            raise FeedError("curated payload contains forbidden field")
        return {field: (str(getattr(row, field)) if field == "resource_uuid" else getattr(row, field)) for field in cls._FIELDS}

    @staticmethod
    def _contains_pii(value):
        names = {"nip", "email", "email_dinas", "nama", "nama_lengkap", "access_token", "token"}
        if isinstance(value, dict):
            return any(str(k).lower() in names or DeltaFeedService._contains_pii(v) for k, v in value.items())
        return any(DeltaFeedService._contains_pii(v) for v in value) if isinstance(value, (list, tuple)) else False


__all__ = ["DeltaFeedService", "FeedPage", "FeedError", "PageLimitError", "ReplayExpiredError"]

# CursorError remains the public expiry error from the signer.
ReplayExpiredError = CursorError
