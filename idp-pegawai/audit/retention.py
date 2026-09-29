from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class RetentionPolicy:
    years: dict[str, int] | None = None

    def __post_init__(self) -> None:
        if self.years is None:
            object.__setattr__(self, "years", {"security_access": 5, "identity_business": 5, "import_governance": 2, "audit_export_governance": 5})

    def boundary(self, retention_class: str, now: datetime) -> datetime:
        years_map = self.years or {}
        try:
            years = years_map[retention_class]
        except KeyError as exc:
            raise ValueError("kelas retensi tidak dikenal") from exc
        return now - timedelta(days=365 * years)


def purge_candidates(rows: list[dict[str, Any]], *, now: datetime | None = None, policy: RetentionPolicy | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    policy = policy or RetentionPolicy()
    return [row for row in rows if not row.get("legal_hold", False) and row["occurred_at"] < policy.boundary(row["retention_class"], now)]
