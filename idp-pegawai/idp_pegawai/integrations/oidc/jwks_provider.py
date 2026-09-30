"""JWKS provider: Peringkat 1 (fetch Keycloak + cache) with Peringkat 2 file fallback.

Best-practice order:
1) Fetch dinamis dari Keycloak certs endpoint + cache TTL (Peringkat 1) — Zero-Maintenance, rotasi aman.
2) File pub_certs.json (Peringkat 2) — rapi, air-gapped.
3) Legacy string env (sudah di-handle di config.py) — tidak dipakai lagi di path baru.

Provider ini fail-closed + bounded: tidak pernah bocorkan secret, mencegah SSRF,
overlap key selama rotasi (cache diperbarui atomically), dan tidak memblokir
validator (validator tetap menerima jwks dict, provider hanya sumbernya).
"""
from __future__ import annotations

import json
import time
import threading
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from flask import current_app

# Internal cache — per-process, thread-safe
_lock = threading.Lock()
_cached_jwks: dict[str, Any] | None = None  # normalized kid->JWK OR raw fallback? store normalized?
_cached_raw: dict | None = None  # raw {"keys": [...]}
_cached_at: float = 0.0
_cached_url: str = ""


def _normalize(raw: dict) -> Mapping[str, Any]:
    """Normalize {"keys": [...]} -> {kid: jwk} seperti Config.INTERNAL_PROFILE_JWKS."""
    if not isinstance(raw, dict):
        return {}
    keys = raw.get("keys")
    if not isinstance(keys, list):
        # Already normalized or empty — kembalikan apa adanya jika sudah mapping
        return raw if all(isinstance(k, dict) and k.get("kid") for k in []) else raw
    out: dict[str, Any] = {}
    for key in keys:
        if isinstance(key, dict) and key.get("kid"):
            out[str(key["kid"])] = key
    return out


def _resolve_jwks_url(app) -> str:
    """Tentukan JWKS URL: explicit config atau derived dari KEYCLOAK_URL/REALM."""
    explicit = (app.config.get("INTERNAL_PROFILE_JWKS_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    base = (app.config.get("KEYCLOAK_URL") or "").strip().rstrip("/")
    realm = (app.config.get("KEYCLOAK_REALM") or "").strip()
    if base and realm:
        # Keycloak standard certs endpoint
        return f"{base}/realms/{realm}/protocol/openid-connect/certs"
    return ""


def _is_url_allowed(url: str, app) -> bool:
    """Guard SSRF minimal: hanya https atau http bila allow_insecure_dev."""
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"https", "http"}:
            return False
        if not parsed.hostname:
            return False
        if parsed.scheme == "http" and not bool(app.config.get("KEYCLOAK_ALLOW_INSECURE_DEV")):
            return False
        # Tolak URL dengan kredensial
        if parsed.username or parsed.password:
            return False
        return True
    except Exception:
        return False


def _resolve_jwks_path(app) -> Path | None:
    """Resolve file path relatif terhadap idp-pegawai/ atau CWD."""
    raw_path = (app.config.get("INTERNAL_PROFILE_JWKS_PATH") or "pub_certs.json").strip()
    if not raw_path:
        return None
    p = Path(raw_path)
    if p.is_absolute():
        return p
    # Coba relatif terhadap package parent (idp-pegawai/)
    from idp_pegawai.config import BASE_DIR  # idp_pegawai/

    candidate = (BASE_DIR.parent / p).resolve()
    if candidate.exists():
        return candidate
    cwd_candidate = (Path.cwd() / p).resolve()
    if cwd_candidate.exists():
        return cwd_candidate
    return candidate  # default meski belum ada — untuk pesan error yang jelas


def _load_from_file(app) -> dict | None:
    path = _resolve_jwks_path(app)
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _fetch_from_keycloak(url: str, timeout: float = 5.0) -> dict | None:
    try:
        req = Request(url, headers={"Accept": "application/json"}, method="GET")
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            data = json.loads(body)
            if isinstance(data, dict) and isinstance(data.get("keys"), list):
                return data
            return None
    except Exception:
        return None


def get_jwks(app=None, *, force_refresh: bool = False) -> Mapping[str, Any]:
    """Ambil JWKS ternormalisasi {kid: jwk} dengan strategi cache.

    Urutan:
      1) Jika FETCH_ENABLED dan URL valid -> fetch dengan TTL, cache in-memory.
         Gagal fetch -> fallback ke cache lama (overlap) atau file.
      2) File pub_certs.json (Peringkat 2).
      3) Config.INTERNAL_PROFILE_JWKS (sudah diisi saat startup dari file/legacy).
    """
    _app = app or current_app
    # Fast path: jika fetch dimatikan, langsung file/config
    fetch_enabled = bool(_app.config.get("INTERNAL_PROFILE_JWKS_FETCH_ENABLED"))
    ttl = int(_app.config.get("INTERNAL_PROFILE_JWKS_CACHE_TTL") or 3600)
    url = _resolve_jwks_url(_app) if fetch_enabled else ""

    global _cached_jwks, _cached_raw, _cached_at, _cached_url

    # Jika fetch enabled, cek cache dulu
    if fetch_enabled and url and _is_url_allowed(url, _app):
        now = time.monotonic()
        with _lock:
            if not force_refresh and _cached_jwks is not None and _cached_raw is not None:
                if _cached_url == url and (now - _cached_at) < ttl:
                    return _cached_jwks
        # Fetch di luar lock agar tidak blokir
        raw = _fetch_from_keycloak(url)
        if raw is not None:
            normalized = _normalize(raw)
            # Simpan atomically di bawah lock; overlap lama tetap dipakai bila fetch gagal
            with _lock:
                _cached_raw = raw
                _cached_jwks = normalized  # type: ignore[assignment]
                _cached_at = now
                _cached_url = url
                # Opsional: tulis balik ke file sebagai cache persisten (best-effort, tidak wajib)
                # — hanya bila path writable; gagal diam saja
                try:
                    path = _resolve_jwks_path(_app)
                    if path is not None:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                except Exception:
                    pass
            return normalized
        # Fetch gagal -> fallback ke cache lama bila masih ada (overlap rotasi)
        with _lock:
            if _cached_jwks is not None and _cached_url == url:
                return _cached_jwks

    # Fallback Peringkat 2: file
    raw_file = _load_from_file(_app)
    if raw_file is not None:
        return _normalize(raw_file)

    # Fallback terakhir: yang sudah di-load di config saat startup
    fallback = _app.config.get("INTERNAL_PROFILE_JWKS") or {}
    if isinstance(fallback, dict):
        # Config sudah normalized {kid: jwk}; kembalikan langsung
        return fallback
    return {}


def invalidate_cache() -> None:
    """Untuk test: kosongkan cache in-memory."""
    global _cached_jwks, _cached_raw, _cached_at, _cached_url
    with _lock:
        _cached_jwks = None
        _cached_raw = None
        _cached_at = 0.0
        _cached_url = ""


__all__ = ["get_jwks", "invalidate_cache", "_normalize", "_resolve_jwks_url"]
