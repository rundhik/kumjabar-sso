"""Integration — lockout di Postgres nyata (Slice 3)."""
import os
import uuid

import pytest

from idp_pegawai import create_app
from idp_pegawai.extensions import db
from idp_pegawai.models.idp_user import IdpUser
from idp_pegawai.services.auth_service import authenticate


def _app():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL belum dikonfigurasi")
    return create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": url, "SECRET_KEY": "test-secret-xxxx-32chars"}), url


@pytest.mark.integration
@pytest.mark.postgresql
def test_auth_service_lockout_postgres():
    app, _ = _app()
    with app.app_context():
        from pathlib import Path
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command

        migrations = str(Path(__file__).parents[3] / "migrations")
        cfg = AlembicConfig(str(Path(__file__).parents[3] / "alembic.ini"))
        cfg.set_main_option("script_location", migrations)
        cfg.set_main_option("sqlalchemy.url", app.config["SQLALCHEMY_DATABASE_URI"])
        alembic_command.upgrade(cfg, "head")

        from idp_pegawai.repositories.idp_user_repository import IdpUserRepository

        uniq = uuid.uuid4().hex[:8]
        u = IdpUser(username=f"authlock_{uniq}", role="operator")
        u.set_password("Str0ng!Pass#12")
        db.session.add(u)
        db.session.commit()
        uid = u.id
        repo = IdpUserRepository(db.session)
        captcha_ok = lambda cid, ans: True

        # 5 gagal -> locked
        for i in range(5):
            res = authenticate(username=u.username, password="WrongPass!123", captcha_id="x", captcha_answer="y", ip="127.0.0.1", db_session=db.session, user_repo=repo, captcha_verify_fn=captcha_ok, config=app.config)
            assert res["ok"] is False

        u2 = db.session.get(IdpUser, uid)
        assert u2.is_locked is True

        # sukses saat locked harus tetap locked
        res = authenticate(username=u.username, password="Str0ng!Pass#12", captcha_id="x", captcha_answer="y", ip="127.0.0.1", db_session=db.session, user_repo=repo, captcha_verify_fn=captcha_ok, config=app.config)
        assert res["code"] == "locked"

        # manual unlock
        u2.locked_until = None
        u2.failed_attempts = 0
        db.session.commit()

        res = authenticate(username=u.username, password="Str0ng!Pass#12", captcha_id="x", captcha_answer="y", ip="127.0.0.1", db_session=db.session, user_repo=repo, captcha_verify_fn=captcha_ok, config=app.config)
        assert res["ok"] is True
        u3 = db.session.get(IdpUser, uid)
        assert u3.failed_attempts == 0

        # cleanup
        db.session.delete(u3)
        db.session.commit()
