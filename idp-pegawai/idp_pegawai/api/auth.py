"""Auth blueprint — Slice 3: GET/POST /login + POST /logout + captcha selalu tampil.

Pisahkan dari ui_bp agar tidak campur capability grants; guard login via session.
"""
from __future__ import annotations

import os
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..security.captcha import generate_captcha, verify_captcha

auth_bp = Blueprint("auth", __name__)

_GENERIC_ERROR = "Username, password, atau captcha salah"
_LOCKED_ERROR = "Akun terkunci, coba lagi setelah beberapa menit"


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        uid = session.get("user_id")
        if not uid:
            # API: JSON, UI: redirect
            if request.accept_mimetypes.best == "application/json" or request.is_json:
                return jsonify({"error": "unauthorized", "code": "login_required"}), 401
            return redirect(url_for("auth.login"))
        # juga cek user masih active (optional, query di request)
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    allowed = {str(r).lower() for r in roles}

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            uid = session.get("user_id")
            if not uid:
                if request.accept_mimetypes.best == "application/json" or request.is_json:
                    return jsonify({"error": "unauthorized", "code": "login_required"}), 401
                return redirect(url_for("auth.login"))
            role = str(session.get("role") or "").lower()
            if role not in allowed:
                if request.accept_mimetypes.best == "application/json" or request.is_json:
                    return jsonify({"error": "forbidden", "code": "role_forbidden"}), 403
                return render_template("ui/denied.html"), 403
            return view(*args, **kwargs)

        return wrapped

    return decorator


def _get_captcha_redis_client():
    """Ambil redis client dari app extensions bila ada."""
    try:
        rc = current_app.extensions.get("redis_client") or current_app.extensions.get("redis")
        if rc:
            return rc
        url = current_app.config.get("REDIS_URL")
        if url and os.getenv("REDIS_URL") != "redis://localhost:6379/0":
            import redis as redis_lib

            return redis_lib.from_url(url, decode_responses=True)
    except Exception:
        pass
    return None


def _new_captcha():
    rc = _get_captcha_redis_client()
    try:
        return generate_captcha(redis_client=rc)
    except Exception:
        return generate_captcha(redis_client=None)


def _resolve_user_repo():
    # allow test injection via app.config["IDP_USER_REPOSITORY"]
    repo = current_app.config.get("IDP_USER_REPOSITORY")
    if repo is not None:
        return repo
    # runtime repo
    try:
        from ..extensions import db

        from ..repositories.idp_user_repository import IdpUserRepository

        return IdpUserRepository(db.session)
    except Exception:
        return None


@auth_bp.get("/login")
def login():
    captcha = _new_captcha()
    return render_template(
        "auth/login.html",
        captcha_id=captcha["captcha_id"],
        captcha_image=captcha["image_base64"],
        error=None,
    )


@auth_bp.post("/login")
def login_post():
    # support JSON dan form
    if request.is_json:
        data = request.get_json(silent=True) or {}
        username = data.get("username", "")
        password = data.get("password", "")
        captcha_id = data.get("captcha_id", "")
        captcha_answer = data.get("captcha_answer", "") or data.get("captcha", "")
    else:
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        captcha_id = request.form.get("captcha_id", "")
        captcha_answer = request.form.get("captcha_answer", "") or request.form.get("captcha", "")

    rc = _get_captcha_redis_client()
    # verify captcha via service — pakai client yang sama dengan generate
    def _verify(cid, ans):
        try:
            return verify_captcha(cid, ans, redis_client=rc)
        except Exception:
            return False

    from ..services.auth_service import authenticate

    # repo + session untuk transaksi lockout/failed_attempts
    repo = _resolve_user_repo()
    try:
        from ..extensions import db as _db

        db_session = _db.session
    except Exception:
        db_session = None

    # jika repo di-inject dari test (in-memory), db_session mungkin tidak relevan — tetap pass
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    result = authenticate(
        username=username,
        password=password,
        captcha_id=captcha_id,
        captcha_answer=captcha_answer,
        ip=ip,
        db_session=db_session,
        user_repo=repo,
        captcha_verify_fn=_verify,
        config=current_app.config,
    )

    # audit tanpa password/captcha
    try:
        current_app.logger.info("auth %s username=%s ip=%s code=%s", result["audit"].get("event"), result["audit"].get("username"), ip, result.get("code"))
    except Exception:
        pass

    if not result["ok"]:
        captcha = _new_captcha()
        # jaga agar password tidak echo
        if request.is_json:
            return jsonify({"error": result["error"], "code": result["code"]}), 400 if result["code"] in ("captcha_invalid", "invalid_credentials") else 403
        return (
            render_template(
                "auth/login.html",
                captcha_id=captcha["captcha_id"],
                captcha_image=captcha["image_base64"],
                error=result["error"],
            ),
            403 if result["code"] == "locked" else 400,
        )

    # sukses — set session
    user = result["user"]
    session.clear()
    session["user_id"] = int(user.id)
    session["username"] = str(user.username)
    session["role"] = str(getattr(user, "role", "operator")).lower()
    session.permanent = True

    if request.is_json:
        return jsonify({"ok": True, "role": session["role"], "username": session["username"]}), 200

    # redirect role-aware
    nxt = request.args.get("next") or request.form.get("next")
    if nxt and nxt.startswith("/") and not nxt.startswith("//"):
        return redirect(nxt)
    return redirect(url_for("ui.dashboard"))


@auth_bp.post("/logout")
@auth_bp.get("/logout")
def logout():
    session.clear()
    if request.is_json or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": True}), 200
    return redirect(url_for("auth.login"))


__all__ = ["auth_bp", "login_required", "role_required"]
