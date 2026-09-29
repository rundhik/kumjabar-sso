"""Opaque, profile-bound HMAC cursors for consumer feeds."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Mapping


class CursorError(ValueError):
    """Raised for malformed, expired, or incorrectly-bound cursors."""


class CursorSigner:
    VERSION = 1
    QUERY_SHAPE = "changes_v1"
    _PII_NAMES = {"nip", "email", "email_dinas", "nama", "nama_lengkap", "access_token", "token"}

    def __init__(self, *, active_key_id: str, keys: Mapping[str, bytes], ttl: timedelta = timedelta(days=30)):
        if not active_key_id or active_key_id not in keys:
            raise ValueError("active key must be present")
        if not keys or any(not isinstance(k, bytes) or not k for k in keys.values()):
            raise ValueError("keys must contain non-empty bytes")
        self.active_key_id, self.keys, self.ttl = active_key_id, dict(keys), ttl

    @staticmethod
    def _b64(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _unb64(value: str) -> bytes:
        if not value or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in value):
            raise CursorError("invalid cursor encoding")
        try:
            return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        except Exception as exc:
            raise CursorError("invalid cursor encoding") from exc

    def encode(self, *, consumer_code: str, registration_uuid: str, resource_family: str,
               field_profile: str, contract_version: str, query_shape: str = QUERY_SHAPE,
               position: int, issued_at: datetime | None = None, expires_at: datetime | None = None,
               **extra: object) -> str:
        if extra or not all(isinstance(v, str) and v for v in (consumer_code, registration_uuid, resource_family, field_profile, contract_version, query_shape)):
            raise CursorError("invalid cursor claims")
        if not isinstance(position, int) or isinstance(position, bool) or position < 0:
            raise CursorError("invalid cursor position")
        now = issued_at or datetime.now(timezone.utc)
        expiry = expires_at or now + self.ttl
        if not isinstance(now, datetime) or not isinstance(expiry, datetime) or expiry <= now:
            raise CursorError("invalid cursor expiry")
        payload = {"cursor_version": self.VERSION, "consumer_code": consumer_code, "registration_uuid": registration_uuid,
                   "resource_family": resource_family, "field_profile": field_profile, "contract_version": contract_version,
                   "query_shape": query_shape, "position": position, "issued_at": now.astimezone(timezone.utc).isoformat(),
                   "expires_at": expiry.astimezone(timezone.utc).isoformat(), "key_id": self.active_key_id}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        body = self._b64(raw)
        return body + "." + self._b64(hmac.new(self.keys[self.active_key_id], raw, hashlib.sha256).digest())

    def decode(self, token: str, *, consumer_code: str, registration_uuid: str, resource_family: str,
               field_profile: str, contract_version: str, query_shape: str = QUERY_SHAPE,
               now: datetime | None = None) -> dict[str, object]:
        try:
            if not isinstance(token, str) or token.count(".") != 1:
                raise CursorError("invalid cursor")
            body, sig = token.split(".")
            raw = self._unb64(body)
            data = json.loads(raw)
            if not isinstance(data, dict) or set(data) != {"cursor_version", "consumer_code", "registration_uuid", "resource_family", "field_profile", "contract_version", "query_shape", "position", "issued_at", "expires_at", "key_id"}:
                raise CursorError("invalid cursor claims")
            key = self.keys.get(data["key_id"])
            if key is None or not hmac.compare_digest(self._b64(hmac.new(key, raw, hashlib.sha256).digest()), sig):
                raise CursorError("invalid cursor signature")
            if data["cursor_version"] != self.VERSION or any(data[k] != v for k, v in {"consumer_code": consumer_code, "registration_uuid": registration_uuid, "resource_family": resource_family, "field_profile": field_profile, "contract_version": contract_version, "query_shape": query_shape}.items()):
                raise CursorError("invalid cursor binding")
            if not isinstance(data["position"], int) or data["position"] < 0:
                raise CursorError("invalid cursor position")
            expiry = datetime.fromisoformat(data["expires_at"])
            if expiry <= (now or datetime.now(timezone.utc)):
                raise CursorError("cursor expired")
            return data
        except CursorError:
            raise
        except Exception as exc:
            raise CursorError("invalid cursor") from exc

    loads = decode
    dumps = encode
