"""CLI create-admin — Slice 5. Idempotent, validasi password 12/4-kategori."""

from __future__ import annotations

import click
from flask import current_app

from ..models.idp_user import IdpUser
from ..security.password import validate_password_strength


def _get_repo():
    # test injection
    repo = current_app.config.get("IDP_USER_REPOSITORY")
    if repo is not None:
        return repo
    from ..extensions import db
    from ..repositories.idp_user_repository import IdpUserRepository

    return IdpUserRepository(db.session)


def register_cli(app):
    @app.cli.command("create-admin")
    @click.option("--username", required=True, help="Username admin (3-80, lower)")
    @click.option("--password", required=True, help="Password (min 12, 4 kategori)")
    @click.option("--role", default="admin", show_default=True, type=click.Choice(["admin", "operator"], case_sensitive=False))
    @click.option("--email", default=None, help="Email opsional")
    def create_admin(username: str, password: str, role: str, email):
        """Buat user admin/operator pertama (idempotent)."""
        from ..extensions import db

        username_norm = str(username).strip().lower()
        role_norm = str(role).strip().lower()
        errors = validate_password_strength(password, username=username_norm, email=email or "")
        if errors:
            click.echo("[ERROR] Password tidak memenuhi kriteria:", err=True)
            for e in errors:
                click.echo(f"  - {e}", err=True)
            raise SystemExit(1)

        repo = _get_repo()
        existing = repo.get_by_username(username_norm)
        if existing is not None:
            click.echo(f"[SKIP] username '{username_norm}' already exists (id={existing.id}, role={existing.role})")
            return

        # buat via model
        try:
            user = IdpUser(username=username_norm, email=email, role=role_norm)
            user.set_password(password)
            # untuk repo fake (test) tidak perlu db.session
            if hasattr(repo, "session") and hasattr(repo.session, "add"):
                repo.session.add(user)
                repo.session.commit()
            else:
                # repo fake in-memory: simpan manual (untuk test CLI integration tanpa db)
                # fallback: pakai db.session bila ada
                db.session.add(user)
                db.session.commit()
                user = db.session.get(IdpUser, user.id) or user
            # untuk repo fake yang tidak auto-assign id, set fake
            if getattr(user, "id", None) is None:
                # fake repo path
                if hasattr(repo, "_by_name"):
                    user.id = max([u.id for u in repo._by_name.values()], default=0) + 1  # type: ignore
                    repo._by_name[username_norm] = user  # type: ignore
            click.echo(f"[OK] {role_norm} created (username={username_norm}, id={getattr(user, 'id', '?')})")
        except SystemExit:
            raise
        except Exception as exc:
            try:
                db.session.rollback()
            except Exception:
                pass
            click.echo(f"[ERROR] gagal create-admin: {exc}", err=True)
            raise SystemExit(1) from exc
