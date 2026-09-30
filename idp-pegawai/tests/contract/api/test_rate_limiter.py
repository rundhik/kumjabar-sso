"""Contract — rate limiter per-IP 10/menit + login_required/role_required (Slice 4)."""

import pytest

from idp_pegawai import create_app
from idp_pegawai.models.idp_user import IdpUser


class FakeUserRepo:
    def __init__(self, users):
        self._by_name = {u.username.lower(): u for u in users}

    def get_by_username(self, username: str):
        return self._by_name.get(str(username).strip().lower()) if username else None

    def get_by_id(self, user_id: int):
        for u in self._by_name.values():
            if int(u.id) == int(user_id):
                return u
        return None


def _make_user(uid: int, username: str, role: str) -> IdpUser:
    u = IdpUser(username=username, role=role)
    u.id = uid  # type: ignore
    u.set_password("Str0ng!Pass#12")
    u.failed_attempts = 0
    u.locked_until = None
    u.is_active = True
    u.deleted_at = None
    return u


def _new_captcha():
    from idp_pegawai.security import captcha as cap_mod

    cap = cap_mod.generate_captcha(redis_client=None)
    ans = cap_mod._fallback_store[f"captcha:{cap['captcha_id']}"]
    return cap, ans


def test_rate_limiter_login_10_per_minute():
    # TESTING=False agar limiter aktif; pakai sqlite in-memory tapi jangan create_all penuh
    cfg = {
        "TESTING": False,
        "WTF_CSRF_ENABLED": False,
        "RATE_LIMIT_DISABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test-secret-xxxx-32chars-long-xxxxxx",
        "RATE_LIMIT_LOGIN_PER_MINUTE": 10,
    }
    app = create_app(cfg)
    admin = _make_user(1, "testadmin", "admin")
    app.config["IDP_USER_REPOSITORY"] = FakeUserRepo([admin])
    with app.test_client() as c:
        # 10 hit butuh captcha baru tiap request
        for i in range(10):
            cap, ans = _new_captcha()
            c.post("/login", data={"username": "testadmin", "password": "WrongPass!123", "captcha_id": cap["captcha_id"], "captcha_answer": ans}, environ_base={"REMOTE_ADDR": "10.0.0.1"})
        # ke-11 harus 429
        cap, ans = _new_captcha()
        resp = c.post("/login", data={"username": "testadmin", "password": "WrongPass!123", "captcha_id": cap["captcha_id"], "captcha_answer": ans}, environ_base={"REMOTE_ADDR": "10.0.0.1"})
        assert resp.status_code == 429
        assert resp.get_json()["code"] == "rate_limited"


def test_login_required_and_role_required():
    from idp_pegawai.api.auth import login_required, role_required

    cfg = {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "SECRET_KEY": "test-secret-xxxx-32chars-long-xxxxxx"}
    app = create_app(cfg)
    admin = _make_user(1, "admin1", "admin")
    operator = _make_user(2, "op1", "operator")
    # endpoint demo untuk test decorator
    repo_fake = FakeUserRepo([admin, operator])

    @app.get("/demo/login-only")
    @login_required
    def demo_login_only():
        return {"ok": True}

    @app.get("/demo/admin-only")
    @role_required("admin")
    def demo_admin_only():
        return {"ok": True}

    with app.test_client() as c:
        # tanpa session -> redirect atau 401
        resp = c.get("/demo/login-only")
        assert resp.status_code in (302, 401)
        resp = c.get("/demo/admin-only")
        assert resp.status_code in (302, 401, 403)

        # sebagai operator -> login-only OK, admin-only 403
        # buat session operator via login
        cap, ans = _new_captcha()
        app.config["IDP_USER_REPOSITORY"] = repo_fake
        c.post("/login", data={"username": "op1", "password": "Str0ng!Pass#12", "captcha_id": cap["captcha_id"], "captcha_answer": ans})
        assert c.get("/demo/login-only").status_code == 200
        assert c.get("/demo/admin-only").status_code == 403

        # sebagai admin -> admin-only OK
        c.post("/logout")
        cap, ans = _new_captcha()
        c.post("/login", data={"username": "admin1", "password": "Str0ng!Pass#12", "captcha_id": cap["captcha_id"], "captcha_answer": ans})
        assert c.get("/demo/admin-only").status_code == 200
