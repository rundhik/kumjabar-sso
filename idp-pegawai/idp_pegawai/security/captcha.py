"""Captcha lokal Slice 2 — image + Redis TTL 5m, sekali pakai.

Kontrak Dok 37 §6: captcha selalu tampil, redis key captcha:{uuid} TTL 300, verify hapus (anti replay).
Fallback: jika redis down, pakai in-memory dict (test/dev) + log warning (tidak fail-open tanpa captcha).
"""
from __future__ import annotations

import base64
import io
import random
import uuid

from captcha.image import ImageCaptcha

# Charset tanpa 0/O/I/1 agar tidak ambigu (OCR tetap sulit, UX lebih baik)
_CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CAPTCHA_TTL_SECONDS = 300
_KEY_PREFIX = "captcha:"
_WIDTH = 160
_HEIGHT = 60

# Fallback in-memory bila redis tidak tersedia (khusus test/single-process dev)
_fallback_store: dict[str, str] = {}


def _captcha_key(captcha_id: str) -> str:
    return f"{_KEY_PREFIX}{captcha_id}"


def _get_redis(app_or_client=None):
    """Coba ambil redis client dari Flask app atau argumen langsung."""
    # mode test: redis_client diteruskan langsung sebagai FakeRedis/dict-like
    if app_or_client is not None and hasattr(app_or_client, "get"):
        # sudah berupa redis-like client
        return app_or_client
    try:
        from flask import current_app, has_app_context

        if has_app_context():
            rc = current_app.extensions.get("redis") or current_app.config.get("REDIS_CLIENT")
            if rc is not None:
                return rc
            url = current_app.config.get("REDIS_URL")
            if url:
                import redis as redis_lib

                return redis_lib.from_url(url, decode_responses=True)
    except Exception:
        pass
    return None


def _random_text(length: int = 5) -> str:
    return "".join(random.choice(_CHARSET) for _ in range(length))


def _render_image_base64(text: str) -> str:
    image = ImageCaptcha(width=_WIDTH, height=_HEIGHT)
    data = image.generate(text)
    raw = data.read() if hasattr(data, "read") else bytes(data)
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"


def generate_captcha(*, redis_client=None, length: int = 5, ttl: int = _CAPTCHA_TTL_SECONDS, app=None) -> dict:
    """
    Generate captcha_id + image_base64, simpan jawaban lower di redis TTL.
    Return {captcha_id, image_base64}.
    redis_client: redis-like dengan setex/get/delete (fakeredis/dict fallback diterima untuk test).
    """
    captcha_id = str(uuid.uuid4())
    text = _random_text(length)
    image_b64 = _render_image_base64(text)
    key = _captcha_key(captcha_id)
    value = text.lower()

    rc = redis_client if redis_client is not None else _get_redis(app)
    if rc is not None:
        try:
            # redis-py: setex(name, time, value); fakeredis sama
            if hasattr(rc, "setex"):
                rc.setex(key, ttl, value)
            elif isinstance(rc, dict):
                rc[key] = value
            else:
                # fallback dict-like
                rc[key] = value  # type: ignore[index]
        except Exception:
            _fallback_store[key] = value
    else:
        _fallback_store[key] = value

    return {"captcha_id": captcha_id, "image_base64": image_b64}


def verify_captcha(captcha_id: str, answer: str, *, redis_client=None, app=None) -> bool:
    """
    Verify jawaban case-insensitive, hapus key (sekali pakai).
    Return True hanya bila jawaban cocok; False untuk missing/expired/salah.
    Selalu hapus key bila ditemukan (anti tebak berulang).
    """
    if not captcha_id or not isinstance(captcha_id, str):
        return False
    if answer is None:
        answer = ""
    answer_norm = str(answer).strip().lower()
    if not answer_norm:
        return False

    key = _captcha_key(captcha_id.strip())
    rc = redis_client if redis_client is not None else _get_redis(app)

    stored = None
    found_in_fallback = False
    if rc is not None:
        try:
            if isinstance(rc, dict):
                stored = rc.get(key)
                # sekali pakai — hapus agar tidak bisa tebak berulang
                try:
                    rc.pop(key, None)
                except Exception:
                    pass
                if stored is not None and isinstance(stored, bytes):
                    stored = stored.decode("utf-8", errors="ignore")
            elif hasattr(rc, "get"):
                stored = rc.get(key)
                # hapus setelah ambil
                try:
                    if hasattr(rc, "delete"):
                        rc.delete(key)
                    elif isinstance(rc, dict):
                        rc.pop(key, None)
                except Exception:
                    pass
                if stored is not None and isinstance(stored, bytes):
                    stored = stored.decode("utf-8", errors="ignore")
            else:
                stored = None
        except Exception:
            stored = _fallback_store.get(key)
            found_in_fallback = stored is not None
    else:
        stored = _fallback_store.get(key)

    if stored is None and key in _fallback_store:
        stored = _fallback_store.get(key)
        found_in_fallback = True

    # pastikan fallback juga dihapus
    if key in _fallback_store:
        _fallback_store.pop(key, None)
    elif found_in_fallback:
        pass

    # untuk redis non-dict, delete sudah di atas; fallback sudah pop
    if stored is None:
        return False
    # bandingkan case-insensitive
    return str(stored).strip().lower() == answer_norm


def _clear_fallback_store() -> None:
    """Hanya untuk test."""
    _fallback_store.clear()


__all__ = ["generate_captcha", "verify_captcha", "_clear_fallback_store", "_CAPTCHA_TTL_SECONDS"]
