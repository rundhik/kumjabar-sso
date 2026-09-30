"""Contract — /admin/users RBAC tipis (Slice 5). Operator 403, admin 200/201."""

from idp_pegawai import create_app
from idp_pegawai.models.idp_user import IdpUser
from idp_pegawai.security import captcha as cap_mod


class FakeUserRepo:
    def __init__(self, users):
        self._by_name = {u.username.lower(): u for u in users}
        self._by_id = {int(u.id): u for u in users}
        self.session = self  # for add/commit fake

    def get_by_username(self, username: str):
        return self._by_name.get(str(username).strip().lower()) if username else None

    def get_by_id(self, user_id: int):
        return self._by_id.get(int(user_id))

    def add(self, user):
        # assign id
        if getattr(user, "id", None) is None or user.id in (None, 0):
            user.id = max(self._by_id.keys(), default=0) + 1
        self._by_name[user.username.lower()] = user
        self._by_id[int(user.id)] = user

    def commit(self):
        pass

    def rollback(self):
        pass


def _make_user(uid: int, username: str, role: str) -> IdpUser:
    u = IdpUser(username=username, role=role)
    u.id = uid  # type: ignore
    u.set_password("Str0ng!Pass#12")
    u.failed_attempts = 0
    u.locked_until = None
    u.is_active = True
    u.deleted_at = None
    return u


def _app_with_fake():
    cfg = {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "SECRET_KEY": "test-secret-xxxx-32chars-long-xxxxxx"}
    app = create_app(cfg)
    admin = _make_user(1, "admin1", "admin")
    operator = _make_user(2, "op1", "operator")
    repo = FakeUserRepo([admin, operator])
    app.config["IDP_USER_REPOSITORY"] = repo
    return app, admin, operator, repo


def _login(app, username: str, password: str = "Str0ng!Pass#12"):
    cap = cap_mod.generate_captcha(redis_client=None)
    ans = cap_mod._fallback_store[f"captcha:{cap['captcha_id']}"]
    with app.test_client() as c:
        c.post("/login", data={"username": username, "password": password, "captcha_id": cap["captcha_id"], "captcha_answer": ans})
        # copy cookies via session
        return c


def test_admin_users_operator_forbidden():
    app, admin, operator, repo = _app_with_fake()
    with app.test_client() as c:
        # login sebagai operator
        cap = cap_mod.generate_captcha(redis_client=None)
        ans = cap_mod._fallback_store[f"captcha:{cap['captcha_id']}"]
        c.post("/login", data={"username": "op1", "password": "Str0ng!Pass#12", "captcha_id": cap["captcha_id"], "captcha_answer": ans})
        resp = c.get("/admin/users", headers={"Accept": "application/json"})
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "role_forbidden"


def test_admin_users_admin_can_list_and_create():
    app, admin, operator, repo = _app_with_fake()
    with app.test_client() as c:
        cap = cap_mod.generate_captcha(redis_client=None)
        ans = cap_mod._fallback_store[f"captcha:{cap['captcha_id']}"]
        c.post("/login", data={"username": "admin1", "password": "Str0ng!Pass#12", "captcha_id": cap["captcha_id"], "captcha_answer": ans})
        resp = c.get("/admin/users", headers={"Accept": "application/json"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

        # create new operator
        resp2 = c.post("/admin/users", json={"username": "newop", "password": "Str0ng!Pass#12", "role": "operator"})
        assert resp2.status_code == 201
        assert resp2.get_json()["username"] == "newop"

        # duplicate -> 409
        resp3 = c.post("/admin/users", json={"username": "newop", "password": "Str0ng!Pass#12", "role": "operator"})
        assert resp3.status_code == 409

        # weak password -> 400
        resp4 = c.post("/admin/users", json={"username": "weak1", "password": "short", "role": "operator"})
        assert resp4.status_code == 400


def test_admin_users_requires_login():
    cfg = {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "SECRET_KEY": "test-secret-xxxx-32chars-long-xxxxxx"}
    app = create_app(cfg)
    app.config["IDP_USER_REPOSITORY"] = FakeUserRepo([_make_user(1, "admin1", "admin")])
    with app.test_client() as c:
        resp = c.get("/admin/users", headers={"Accept": "application/json"})
        assert resp.status_code == 401
