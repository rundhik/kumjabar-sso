"""Transport-neutral consumer freshness and conflict application core."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


class ConsumerApplyError(ValueError):
    """An incoming change cannot be applied safely."""


class ConflictError(ConsumerApplyError):
    """Same resource/version arrived with a different content hash."""


class OutOfOrderError(ConsumerApplyError):
    """A caller requested strict ordering for an older change."""


@dataclass
class ConsumerSnapshot:
    resource_uuid: str
    source_version: int
    payload_hash: str
    payload: dict | None
    tombstone: bool = False


class ConsumerState:
    """Small state machine suitable for wrapping in a consumer DB transaction."""

    def __init__(self):
        self._snapshots: dict[str, ConsumerSnapshot] = {}

    def get(self, resource_uuid: str) -> ConsumerSnapshot | None:
        return self._snapshots.get(str(resource_uuid))

    def apply(self, change: object | dict, *, strict_order: bool = False) -> str:
        value = _as_mapping(change)
        key = str(value["resource_uuid"])
        version = value["source_version"]
        digest = value["payload_hash"]
        current = self._snapshots.get(key)
        if current is not None:
            if version == current.source_version:
                if digest != current.payload_hash:
                    raise ConflictError("same source version has different payload hash")
                return "duplicate"
            if version < current.source_version:
                if strict_order:
                    raise OutOfOrderError("change is older than local snapshot")
                return "stale"
        tombstone = value.get("change_type") == "tombstone"
        if tombstone and value.get("payload") is not None:
            raise ConsumerApplyError("tombstone must not contain payload")
        self._snapshots[key] = ConsumerSnapshot(key, version, digest, deepcopy(value.get("payload")), tombstone)
        return "applied"


def apply_page(state: ConsumerState, changes: Iterable[object | dict]) -> list[str]:
    """Apply a page atomically; restore all state if any item fails."""
    before = deepcopy(state._snapshots)
    try:
        return [state.apply(change) for change in changes]
    except Exception:
        state._snapshots = before
        raise


def classify_freshness(local_version, local_hash, source_version, source_hash, *,
                       now: datetime | None = None, observed_at: datetime | None = None,
                       max_lag: float = 60.0) -> str:
    if local_version is None or local_hash is None or source_version is None or source_hash is None:
        return "unknown"
    if local_version != source_version or local_hash != source_hash:
        return "stale"
    if observed_at is None:
        return "fresh"
    now = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    if (now - observed_at).total_seconds() > max_lag:
        return "lagging"
    return "fresh"


def _as_mapping(change):
    if isinstance(change, dict):
        return change
    return {name: getattr(change, name) for name in
            ("resource_uuid", "source_version", "payload_hash", "payload", "change_type")}


__all__ = ["ConsumerState", "ConsumerSnapshot", "ConflictError", "OutOfOrderError",
           "ConsumerApplyError", "apply_page", "classify_freshness"]
