"""Contract — auth login/logout Slice 3 + captcha selalu tampil + lockout.

Isolasi tanpa Postgres penuh: pakai FakeUserRepo (IdpUser in-memory) + captcha fallback.
"""

import pytest

from idp_pegawai import create_app
from idp_pegawai.extensions import db
from idp_pegawai.models.idp_user import IdpUser
from idp_pegawai.security import captcha as cap_mod


class FakeUserRepo:
    def __init__(self, users):
        self._by_name = {u.username.lower(): u for u in users}
        self._by_id = {u.id: u for u in users}

    def get_by_username(self, username: str):
        if not username:
            return None
        return self._by_name.get(str(username).strip().lower())

    def get_by_id(self, user_id: int):
        return self._by_id.get(user_id)

    def get_by_email(self, email: str):
        if not email:
            return None
        n = str(email).strip().lower()
        for u in self._by_name.values():
            if (u.email or "").lower() == n:
                return u
        return None


def _make_user(uid: int, username: str, role: str, password: str = "Str0ng!Pass#12") -> IdpUser:
    u = IdpUser(username=username, role=role)
    u.id = uid  # type: ignore[attr-defined]
    # pastikan uuid ada (ModelBase default uuid4, tapi kita sudah set via ModelBase)
    u.set_password(password)
    u.failed_attempts = 0
    u.locked_until = None
    u.is_active = True
    u.deleted_at = None
    return u


def _app_with_fake_users():
    cfg = {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "SECRET_KEY": "test-secret-32chars-long-xxxx"}
    app = create_app(cfg)
    # jangan db.create_all (hindari pegawai ~). Cukup set fake repo
    admin = _make_user(1, "testadmin", "admin")
    operator = _make_user(2, "operator1", "operator")
    repo = FakeUserRepo([admin, operator])
    app.config["IDP_USER_REPOSITORY"] = repo
    # simpan refs untuk cek lockout
    app.config["_TEST_USERS"] = {"admin": admin, "operator": operator}
    return app, admin, operator


def _get_captcha():
    cap = cap_mod.generate_captcha(redis_client=None)
    ans = cap_mod._fallback_store[f"captcha:{cap['captcha_id']}"]
    return cap, ans


class TestLoginGet:
    def test_get_login_contains_captcha(self):
        app, *_ = _app_with_fake_users()
        with app.test_client() as c:
            resp = c.get("/login")
            assert resp.status_code == 200
            html = resp.data.decode()
            assert "captcha" in html.lower()
            assert "captcha_id" in html.lower()
            assert "data:image/png;base64" in html


class TestLoginPost:
    def test_post_without_captcha_rejected_generic(self):
        app, *_ = _app_with_fake_users()
        with app.test_client() as c:
            resp = c.post("/login", data={"username": "testadmin", "password": "Str0ng!Pass#12", "captcha_id": "", "captcha_answer": ""})
            assert resp.status_code in (400, 403)
            assert "Username, password, atau captcha salah" in resp.data.decode()

    def test_post_wrong_captcha_rejected(self):
        app, *_ = _app_with_fake_users()
        with app.test_client() as c:
            cap, _ = _get_captcha()
            resp = c.post("/login", data={"username": "testadmin", "password": "Str0ng!Pass#12", "captcha_id": cap["captcha_id"], "captcha_answer": "WRONG"})
            assert resp.status_code in (400, 403)
            assert "Username, password, atau captcha salah" in resp.data.decode()

    def test_post_wrong_password_generic_and_increments(self):
        app, admin, _ = _app_with_fake_users()
        with app.test_client() as c:
            cap, ans = _get_captcha()
            resp = c.post("/login", data={"username": "testadmin", "password": "WrongPass!123", "captcha_id": cap["captcha_id"], "captcha_answer": ans})
            assert resp.status_code in (400, 403)
            assert "Username, password, atau captcha salah" in resp.data.decode()
            assert admin.failed_attempts >= 1

    def test_lockout_after_5_fails(self):
        app, admin, _ = _app_with_fake_users()
        with app.test_client() as c:
            for i in range(5):
                cap, ans = _get_captcha()
                c.post("/login", data={"username": "testadmin", "password": "WrongPass!123", "captcha_id": cap["captcha_id"], "captcha_answer": ans})
            cap, ans = _get_captcha()
            resp = c.post("/login", data={"username": "testadmin", "password": "Str0ng!Pass#12", "captcha_id": cap["captcha_id"], "captcha_answer": ans})
            assert resp.status_code == 403
            assert "terkunci" in resp.data.decode().lower()
            assert admin.is_locked is True

    def test_success_resets_and_sets_session(self):
        app, admin, _ = _app_with_fake_users()
        with app.test_client() as c:
            for _ in range(2):
                cap, ans = _get_captcha()
                c.post("/login", data={"username": "testadmin", "password": "WrongPass!123", "captcha_id": cap["captcha_id"], "captcha_answer": ans})
            cap, ans = _get_captcha()
            resp = c.post("/login", data={"username": "testadmin", "password": "Str0ng!Pass#12", "captcha_id": cap["captcha_id"], "captcha_answer": ans})
            assert resp.status_code in (200, 302)
            with c.session_transaction() as sess:
                assert sess.get("user_id") == admin.id
                assert sess.get("role") == "admin"
            assert admin.failed_attempts == 0
            assert admin.last_login_at is not None

    def test_xss_payload_escaped(self):
        app, *_ = _app_with_fake_users()
        with app.test_client() as c:
            cap, ans = _get_captcha()
            payload = "<script>alert(1)</script>"
            resp = c.post("/login", data={"username": payload, "password": "Str0ng!Pass#12", "captcha_id": cap["captcha_id"], "captcha_answer": ans})
            html = resp.data.decode()
            assert "<script>alert(1)</script>" not in html

    def test_json_login_success(self):
        app, admin, _ = _app_with_fake_users()
        with app.test_client() as c:
            cap, ans = _get_captcha()
            resp = c.post("/login", json={"username": "testadmin", "password": "Str0ng!Pass#12", "captcha_id": cap["captcha_id"], "captcha_answer": ans})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True

    def test_logout_clears_session(self):
        app, admin, _ = _app_with_fake_users()
        with app.test_client() as c:
            cap, ans = _get_captcha()
            c.post("/login", data={"username": "testadmin", "password": "Str0ng!Pass#12", "captcha_id": cap["captcha_id"], "captcha_answer": ans})
            with c.session_transaction() as sess:
                assert sess.get("user_id") == admin.id
            resp = c.post("/logout")
            assert resp.status_code in (200, 302)
            with c.session_transaction() as sess:
                assert sess.get("user_id") is None
