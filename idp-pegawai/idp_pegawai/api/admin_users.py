"""Admin users — Slice 5: GET/POST /admin/users + deactivate (admin only)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template, request, session

from ..security.sanitization import sanitize_text

admin_users_bp = Blueprint("admin_users", __name__, url_prefix="/admin")


def _require_admin():
    uid = session.get("user_id")
    if not uid:
        if request.accept_mimetypes.best == "application/json" or request.is_json:
            return jsonify({"error": "unauthorized", "code": "login_required"}), 401
        from flask import redirect, url_for

        return redirect(url_for("auth.login"))
    if str(session.get("role") or "").lower() != "admin":
        if request.accept_mimetypes.best == "application/json" or request.is_json:
            return jsonify({"error": "forbidden", "code": "role_forbidden"}), 403
        return render_template("ui/denied.html"), 403
    return None


def _get_repo():
    repo = current_app.config.get("IDP_USER_REPOSITORY")
    if repo is not None:
        return repo
    try:
        from ..extensions import db
        from ..repositories.idp_user_repository import IdpUserRepository

        return IdpUserRepository(db.session)
    except Exception:
        return None


@admin_users_bp.get("/users")
def list_users():
    guard = _require_admin()
    if guard is not None:
        return guard
    repo = _get_repo()
    # ambil semua via session query (pakai model langsung jika repo fake tidak punya list)
    try:
        from ..extensions import db
        from ..models.idp_user import IdpUser

        users = db.session.query(IdpUser).order_by(IdpUser.id).all()
    except Exception:
        # fallback repo fake
        users = list(getattr(repo, "_by_name", {}).values()) if repo else []
    if request.accept_mimetypes.best == "application/json" or request.is_json:
        return jsonify([{"id": u.id, "username": u.username, "email": u.email, "role": u.role, "is_active": u.is_active} for u in users])
    return render_template("admin/users.html", users=users)


@admin_users_bp.post("/users")
def create_user():
    guard = _require_admin()
    if guard is not None:
        return guard
    data = request.get_json(silent=True) if request.is_json else request.form
    username = sanitize_text((data.get("username") or ""), max_length=80).strip().lower() if data else ""
    password = (data.get("password") or "") if data else ""
    role = sanitize_text((data.get("role") or "operator"), max_length=20).strip().lower() if data else "operator"
    email = sanitize_text((data.get("email") or ""), max_length=255).strip().lower() if data and data.get("email") else None
    if email == "":
        email = None

    if not username or not password:
        msg = "Username dan password wajib diisi"
        if request.is_json:
            return jsonify({"error": msg, "code": "validation_error"}), 400
        return render_template("admin/users.html", users=[], error=msg), 400

    if role not in ("admin", "operator"):
        msg = "Role harus admin atau operator"
        if request.is_json:
            return jsonify({"error": msg, "code": "validation_error"}), 400
        return render_template("admin/users.html", users=[], error=msg), 400

    from ..security.password import validate_password_strength

    errs = validate_password_strength(password, username=username, email=email or "")
    if errs:
        msg = "; ".join(errs)
        if request.is_json:
            return jsonify({"error": msg, "code": "weak_password", "details": errs}), 400
        return render_template("admin/users.html", users=[], error=msg), 400

    repo = _get_repo()
    if repo is None:
        return jsonify({"error": "repository tidak tersedia", "code": "internal"}), 500

    # duplicate check
    existing = None
    try:
        existing = repo.get_by_username(username)
    except Exception:
        pass
    if existing is not None:
        msg = "Username sudah ada"
        if request.is_json:
            return jsonify({"error": msg, "code": "duplicate"}), 409
        return render_template("admin/users.html", users=[], error=msg), 409

    # create
    try:
        from ..extensions import db
        from ..models.idp_user import IdpUser

        user = IdpUser(username=username, email=email, role=role)
        user.set_password(password)
        # jika repo punya session (real), pakai repo.session, else db.session
        sess = getattr(repo, "session", db.session)
        sess.add(user)
        sess.commit()
        current_app.logger.info("user_created username=%s role=%s by=%s", username, role, session.get("username"))
        if request.is_json:
            return jsonify({"ok": True, "id": user.id, "username": user.username, "role": user.role}), 201
        from flask import redirect, url_for

        return redirect(url_for("admin_users.list_users"))
    except Exception as exc:
        try:
            from ..extensions import db as _db

            _db.session.rollback()
        except Exception:
            pass
        msg = f"Gagal buat user: {exc}"
        if request.is_json:
            return jsonify({"error": msg, "code": "internal"}), 500
        return render_template("admin/users.html", users=[], error=msg), 500


@admin_users_bp.post("/users/<int:user_id>/deactivate")
def deactivate_user(user_id: int):
    guard = _require_admin()
    if guard is not None:
        return guard
    repo = _get_repo()
    if repo is None:
        return jsonify({"error": "repository tidak tersedia", "code": "internal"}), 500
    # cari user
    target = None
    try:
        from ..extensions import db
        from ..models.idp_user import IdpUser

        target = db.session.get(IdpUser, user_id)
    except Exception:
        try:
            target = repo.get_by_id(user_id)
        except Exception:
            target = None
    if target is None:
        return jsonify({"error": "user tidak ditemukan", "code": "not_found"}), 404
    try:
        from datetime import datetime, timezone

        from ..extensions import db as _db

        target.is_active = False
        target.deleted_at = datetime.now(timezone.utc)
        _db.session.commit()
        current_app.logger.info("user_deactivated id=%s username=%s by=%s", user_id, getattr(target, "username", ""), session.get("username"))
        if request.is_json:
            return jsonify({"ok": True}), 200
        from flask import redirect, url_for

        return redirect(url_for("admin_users.list_users"))
    except Exception as exc:
        try:
            from ..extensions import db as _db2

            _db2.session.rollback()
        except Exception:
            pass
        return jsonify({"error": str(exc), "code": "internal"}), 500


@admin_users_bp.post("/users/<int:user_id>/activate")
def activate_user(user_id: int):
    """Aktifkan kembali user nonaktif."""
    guard = _require_admin()
    if guard is not None:
        return guard
    try:
        from ..extensions import db
        from ..models.idp_user import IdpUser

        target = db.session.get(IdpUser, user_id)
    except Exception:
        target = None
    if target is None:
        return jsonify({"error": "user tidak ditemukan", "code": "not_found"}), 404
    try:
        from ..extensions import db as _db

        target.is_active = True
        target.deleted_at = None
        _db.session.commit()
        current_app.logger.info("user_activated id=%s username=%s by=%s", user_id, getattr(target, "username", ""), session.get("username"))
        if request.is_json:
            return jsonify({"ok": True}), 200
        from flask import redirect, url_for

        return redirect(url_for("admin_users.list_users"))
    except Exception as exc:
        try:
            from ..extensions import db as _db2

            _db2.session.rollback()
        except Exception:
            pass
        return jsonify({"error": str(exc), "code": "internal"}), 500
