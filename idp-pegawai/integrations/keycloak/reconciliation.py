"""Pure, transport-injected managed projection reconciliation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReconciliationResult:
    status: str
    managed_drift: dict[str, dict[str, Any]]
    unmanaged_drift: dict[str, list[str]]


def _values(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple)) else [value]
    return sorted({str(item).strip() for item in values})


def _attrs(value: Any) -> dict[str, list[str]]:
    return value if isinstance(value, dict) else {}


def reconcile(adapter: Any, subject: str, desired_attributes: dict[str, Any], *, expected_identity: str | None, desired_enabled: bool | None = None) -> ReconciliationResult:
    """Read, compare managed state, and repair only safe managed drift.

    ``expected_identity`` is mandatory in practice: a marker mismatch blocks before PUT.
    The returned drift describes the pre-repair state, while unmanaged attributes are
    never part of the mutation contract.
    """
    adapter._authorize()
    current = adapter._read(subject)
    actual = _attrs(current.get("attributes"))
    marker = _values(actual.get("idp_pegawai_uuid"))
    if expected_identity is not None and marker != [str(expected_identity).strip()]:
        return ReconciliationResult("blocked_identity_mismatch", {}, {})

    managed = {str(k): _values(v) for k, v in desired_attributes.items()}
    managed_drift: dict[str, dict[str, Any]] = {}
    for key in set(managed) | ({"enabled"} if desired_enabled is not None else set()):
        want = bool(desired_enabled) if key == "enabled" else managed.get(key, [])
        have = bool(current.get("enabled")) if key == "enabled" else _values(actual.get(key))
        if have != want:
            managed_drift[key] = {"actual": have, "desired": want}

    unmanaged = {k: _values(v) for k, v in actual.items() if k not in managed}
    if not managed_drift:
        return ReconciliationResult("in_sync", {}, {})

    payload = {k: v for k, v in current.items() if k not in adapter._EXCLUDED}
    merged = {k: _values(v) for k, v in actual.items() if k not in managed}
    merged.update(managed)
    payload["attributes"] = merged
    if desired_enabled is not None:
        payload["enabled"] = bool(desired_enabled)
    adapter.transport.request("PUT", adapter.policy.user_url(subject), token=adapter.credential, json=payload)
    final = adapter._read(subject)
    final_attrs = _attrs(final.get("attributes"))
    verified = all((_values(final_attrs.get(k)) if k != "enabled" else bool(final.get(k))) == d["desired"] for k, d in managed_drift.items())
    return ReconciliationResult("repaired" if verified else "drifted", managed_drift, unmanaged)


__all__ = ["ReconciliationResult", "reconcile"]
