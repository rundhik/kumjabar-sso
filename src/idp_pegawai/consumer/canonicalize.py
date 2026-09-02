"""Deterministic, Unicode-safe canonical JSON and profile hash."""
import hashlib
import json
import math
import unicodedata
from datetime import datetime, timezone


def _normalize(value):
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite number")
    return value


def canonical_json(data: dict) -> str:
    return json.dumps(_normalize(data), ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False)


def canonical_hash(data: dict) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def canonical_timestamp(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp requires timezone")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
