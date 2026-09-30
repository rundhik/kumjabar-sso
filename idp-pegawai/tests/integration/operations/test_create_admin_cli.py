"""Integration — CLI create-admin idempotent (Slice 5) di Postgres nyata."""
import os
import uuid

import pytest

from idp_pegawai import create_app
from idp_pegawai.extensions import db
from idp_pegawai.models.idp_user import IdpUser


def _app():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL belum dikonfigurasi")
    return create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": url, "SECRET_KEY": "test-secret-xxxx-32chars"}), url


@pytest.mark.integration
@pytest.mark.postgresql
def test_create_admin_cli_idempotent_postgres():
    app, _ = _app()
    uniq = uuid.uuid4().hex[:6]
    username = f"cliadmin_{uniq}"
    password = "Str0ng!Pass#12"
    runner = app.test_cli_runner()

    with app.app_context():
        from pathlib import Path
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command

        migrations = str(Path(__file__).parents[3] / "migrations")
        cfg = AlembicConfig(str(Path(__file__).parents[3] / "alembic.ini"))
        cfg.set_main_option("script_location", migrations)
        cfg.set_main_option("sqlalchemy.url", app.config["SQLALCHEMY_DATABASE_URI"])
        alembic_command.upgrade(cfg, "head")

        # 1. create
        result = runner.invoke(args=["create-admin", "--username", username, "--password", password, "--role", "admin"])
        assert result.exit_code == 0, result.output
        assert "[OK]" in result.output

        # 2. idempotent second run
        result2 = runner.invoke(args=["create-admin", "--username", username, "--password", password, "--role", "admin"])
        assert result2.exit_code == 0, result2.output
        assert "[SKIP]" in result2.output

        # 3. weak password harus error
        result3 = runner.invoke(args=["create-admin", "--username", f"weak_{uniq}", "--password", "short", "--role", "operator"])
        assert result3.exit_code != 0
        assert "Password" in result3.output

        # verify user exists
        u = db.session.query(IdpUser).filter_by(username=username.lower()).first()
        assert u is not None
        assert u.role == "admin"
        assert u.check_password(password) is True

        # cleanup
        db.session.delete(u)
        db.session.commit()
