from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SENSITIVE = {"password", "token", "secret", "authorization", "cookie", "email", "raw_payload", "payload", "nip"}
ALLOWED_METADATA = {"row_count", "success_count", "warning_count", "artifact_uuid", "idempotency_replay"}
MAX_METADATA_STRING = 255


def redact_change_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    def clean(obj: Any, key: str | None = None) -> Any:
        if key and key.lower() in SENSITIVE:
            return None
        if isinstance(obj, Mapping):
            return {k: v for k, raw in obj.items() if (v := clean(raw, str(k))) is not None}
        if isinstance(obj, (list, tuple)):
            return [clean(v) for v in obj]
        return obj
    result = clean(value)
    if not isinstance(result, dict):
        raise ValueError("change_summary harus object")
    return result


def validate_metadata(event_type: str, metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    metadata = dict(metadata or {})
    unknown = set(metadata) - ALLOWED_METADATA
    if unknown or any(k.lower() in SENSITIVE for k in metadata):
        raise ValueError("metadata audit mengandung key terlarang")
    if any(isinstance(v, (Mapping, list, tuple)) for v in metadata.values()):
        raise ValueError("metadata audit tidak boleh nested")
    if any(isinstance(v, str) and len(v) > MAX_METADATA_STRING for v in metadata.values()):
        raise ValueError("metadata audit terlalu besar")
    return metadata


def bounded_summary(summary: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if summary is None:
        return None
    result = redact_change_summary(summary)
    if len(str(result)) > 2048:
        raise ValueError("change_summary terlalu besar")
    return result
