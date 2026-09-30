"""Integration — IdpUser constraints di PostgreSQL nyata."""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from idp_pegawai import create_app
from idp_pegawai.extensions import db
from idp_pegawai.models.idp_user import IdpUser


def _app():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL belum dikonfigurasi")
    return create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": database_url}), database_url


@pytest.mark.integration
@pytest.mark.postgresql
def test_idp_user_create_normal_ok():
    app, _ = _app()
    with app.app_context():
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command
        from pathlib import Path

        # ensure schema exists
        migrations = str(Path(__file__).parents[3] / "migrations")
        cfg = AlembicConfig(str(Path(__file__).parents[3] / "alembic.ini"))
        # fallback: set script_location manually if needed
        cfg.set_main_option("script_location", migrations)
        # use DATABASE_URL from app
        cfg.set_main_option("sqlalchemy.url", app.config["SQLALCHEMY_DATABASE_URI"])
        alembic_command.upgrade(cfg, "head")

        uniq = uuid.uuid4().hex[:8]
        u = IdpUser(username=f"testuser_{uniq}", email=f"test_{uniq}@example.com", role="operator")
        u.set_password("Str0ng!Pass#12")
        db.session.add(u)
        db.session.commit()
        assert u.id is not None
        assert u.uuid is not None
        assert u.username == f"testuser_{uniq}"
        assert u.check_password("Str0ng!Pass#12") is True
        assert u.check_password("wrong") is False
        assert u.is_locked is False
        # cleanup
        db.session.delete(u)
        db.session.commit()


@pytest.mark.integration
@pytest.mark.postgresql
def test_idp_user_duplicate_username_case_insensitive():
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

        uniq = uuid.uuid4().hex[:8]
        base = f"dupuser_{uniq}"
        u1 = IdpUser(username=base, role="operator")
        u1.set_password("Str0ng!Pass#12")
        db.session.add(u1)
        db.session.commit()

        # attempt duplicate with different case — app lowercases, DB lower index should block
        u2 = IdpUser(username=base.upper(), role="operator")
        u2.set_password("Str0ng!Pass#12")
        db.session.add(u2)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        # cleanup
        db.session.delete(u1)
        db.session.commit()


@pytest.mark.integration
@pytest.mark.postgresql
def test_idp_user_role_invalid_check_violation():
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

        # Bypass model validation via raw SQL to test DB check constraint
        with db.engine.begin() as conn:
            with pytest.raises(Exception):
                conn.execute(
                    text(
                        "INSERT INTO idp_users (username, password_hash, role) VALUES (:u, :p, :r)"
                    ),
                    {"u": f"badrole_{uuid.uuid4().hex[:6]}", "p": "hash", "r": "superadmin"},
                )


@pytest.mark.integration
@pytest.mark.postgresql
def test_idp_user_soft_delete_still_queryable():
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

        uniq = uuid.uuid4().hex[:8]
        u = IdpUser(username=f"softdel_{uniq}", role="operator")
        u.set_password("Str0ng!Pass#12")
        db.session.add(u)
        db.session.commit()
        uid = u.id
        u.deleted_at = datetime.now(timezone.utc)
        db.session.commit()

        fetched = db.session.get(IdpUser, uid)
        assert fetched is not None
        assert fetched.deleted_at is not None

        # cleanup hard delete via SQL
        with db.engine.begin() as conn:
            conn.execute(text("DELETE FROM idp_users WHERE id = :id"), {"id": uid})


@pytest.mark.integration
@pytest.mark.postgresql
def test_idp_user_uuid_unique_and_bigint_pk():
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

        uniq = uuid.uuid4().hex[:8]
        u = IdpUser(username=f"uuidtest_{uniq}", role="operator")
        u.set_password("Str0ng!Pass#12")
        db.session.add(u)
        db.session.commit()
        assert isinstance(u.id, int)
        assert u.uuid is not None
        # uuid uniqueness — try insert duplicate uuid via raw SQL
        with db.engine.begin() as conn:
            with pytest.raises(Exception):
                conn.execute(
                    text("INSERT INTO idp_users (username, password_hash, role, uuid) VALUES (:u, :p, :r, :uuid)"),
                    {"u": f"uuiddup_{uniq}", "p": "hash", "r": "operator", "uuid": str(u.uuid)},
                )
        db.session.delete(u)
        db.session.commit()


@pytest.mark.integration
@pytest.mark.postgresql
def test_idp_user_is_locked_and_email_nullable_unique():
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

        uniq = uuid.uuid4().hex[:8]
        # email nullable — two users without email ok
        u1 = IdpUser(username=f"emailless1_{uniq}", role="operator")
        u1.set_password("Str0ng!Pass#12")
        u2 = IdpUser(username=f"emailless2_{uniq}", role="operator")
        u2.set_password("Str0ng!Pass#12")
        db.session.add_all([u1, u2])
        db.session.commit()

        # is_locked
        u1.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        db.session.commit()
        assert u1.is_locked is True
        u1.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()
        assert u1.is_locked is False

        # email unique when filled
        uniq2 = uuid.uuid4().hex[:8]
        email = f"unique_{uniq2}@example.com"
        u3 = IdpUser(username=f"email1_{uniq2}", email=email, role="operator")
        u3.set_password("Str0ng!Pass#12")
        db.session.add(u3)
        db.session.commit()
        u4 = IdpUser(username=f"email2_{uniq2}", email=email, role="operator")
        u4.set_password("Str0ng!Pass#12")
        db.session.add(u4)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

        # cleanup
        for obj in [u1, u2, u3]:
            db.session.delete(obj)
        db.session.commit()
