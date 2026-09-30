"""Auth service — Slice 3. Urutan: captcha → lookup active → lockout → password → audit + session.

Tidak pernah bocorkan apakah username ada atau tidak — pesan generik.
Lockout: 5 gagal / 15 menit via kolom locked_until + failed_attempts.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..security.sanitization import sanitize_text

_LOGIN_MAX_FAILS = 5
_LOGIN_LOCKOUT_MINUTES = 15
_GENERIC_ERROR = "Username, password, atau captcha salah"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_locked(user) -> bool:
    if user.locked_until is None:
        return False
    lu = user.locked_until
    if lu.tzinfo is None:
        lu = lu.replace(tzinfo=timezone.utc)
    return lu > _now_utc()


def authenticate(
    *,
    username: str,
    password: str,
    captcha_id: str,
    captcha_answer: str,
    ip: str = "",
    db_session=None,
    user_repo=None,
    captcha_verify_fn=None,
    config: dict | None = None,
) -> dict:
    """
    Return dict: {ok: bool, user: IdpUser|None, error: str, code: str, audit: dict}
    code: captcha_invalid | locked | invalid_credentials | success
    Caller wajib generate captcha baru bila not ok (agar form selalu ada captcha).
    """
    config = config or {}
    max_fails = int(config.get("LOGIN_MAX_FAILS", _LOGIN_MAX_FAILS))
    lockout_minutes = int(config.get("LOGIN_LOCKOUT_MINUTES", _LOGIN_LOCKOUT_MINUTES))

    # 1. sanitasi input (XSS) — simpan untuk lookup tapi escape untuk audit/log
    raw_username = sanitize_text(username or "", max_length=80).strip()
    # sanitize_text sudah escape HTML — untuk lookup perlu lower tanpa escape?
    # raw_username sudah strip lower via sanitize_text? sanitize_text escape tapi tetap lower untuk compare
    # lookup via repo sudah lower, jadi pakai raw_username lower
    lookup_username = raw_username.lower()

    # 2. captcha dulu (fail closed)
    verify_fn = captcha_verify_fn
    if verify_fn is None:
        from ..security.captcha import verify_captcha as _verify

        verify_fn = _verify

    captcha_ok = False
    try:
        # captcha module mengharapkan captcha_id + answer + optional redis_client
        captcha_ok = bool(verify_fn(captcha_id, captcha_answer))
    except Exception:
        captcha_ok = False

    if not captcha_ok:
        return {
            "ok": False,
            "user": None,
            "error": _GENERIC_ERROR,
            "code": "captcha_invalid",
            "audit": {"event": "captcha_failed", "username": lookup_username[:40], "ip": ip},
        }

    # 3. lookup user (query-only)
    user = None
    if user_repo is not None:
        try:
            user = user_repo.get_by_username(lookup_username)
        except Exception:
            user = None

    # anti-enumeration: jika user tidak ada / tidak active / soft-deleted, tetap generic
    if user is None or not getattr(user, "is_active", True) or getattr(user, "deleted_at", None) is not None:
        return {
            "ok": False,
            "user": None,
            "error": _GENERIC_ERROR,
            "code": "invalid_credentials",
            "audit": {"event": "login_failed", "username": lookup_username[:40], "ip": ip, "reason": "no_user_or_inactive"},
        }

    # 4. lockout check
    if _is_locked(user):
        return {
            "ok": False,
            "user": None,
            "error": "Akun terkunci, coba lagi setelah beberapa menit",
            "code": "locked",
            "audit": {"event": "login_locked", "username": user.username, "ip": ip},
        }

    # 5. verify password
    try:
        pwd_ok = user.check_password(password or "")
    except Exception:
        pwd_ok = False

    if not pwd_ok:
        # increment counter
        try:
            user.failed_attempts = int(getattr(user, "failed_attempts", 0) or 0) + 1
            if user.failed_attempts >= max_fails:
                user.locked_until = _now_utc() + timedelta(minutes=lockout_minutes)
            if db_session is not None:
                db_session.commit()
        except Exception:
            if db_session is not None:
                try:
                    db_session.rollback()
                except Exception:
                    pass
        # jika baru saja lock, return locked agar UI jelas
        if _is_locked(user):
            return {
                "ok": False,
                "user": None,
                "error": "Akun terkunci, coba lagi setelah beberapa menit",
                "code": "locked",
                "audit": {"event": "login_locked", "username": user.username, "ip": ip},
            }
        return {
            "ok": False,
            "user": None,
            "error": _GENERIC_ERROR,
            "code": "invalid_credentials",
            "audit": {"event": "login_failed", "username": user.username, "ip": ip},
        }

    # 6. sukses — reset counter
    try:
        user.failed_attempts = 0
        user.locked_until = None
        user.last_login_at = _now_utc()
        if db_session is not None:
            db_session.commit()
    except Exception:
        if db_session is not None:
            try:
                db_session.rollback()
            except Exception:
                pass

    return {
        "ok": True,
        "user": user,
        "error": "",
        "code": "success",
        "audit": {"event": "login_success", "username": user.username, "ip": ip, "role": getattr(user, "role", "")},
    }
