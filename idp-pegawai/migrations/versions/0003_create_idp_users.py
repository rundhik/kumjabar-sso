"""create idp_users — Slice 1 local auth.

Revision ID: 0003_create_idp_users
Revises: 0002_squashed_import_outbox_identity
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_create_idp_users"
down_revision = "0002_squashed_import_outbox_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "idp_users",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="operator"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("uuid", name="uq_idp_users_uuid"),
        sa.CheckConstraint("role IN ('admin','operator')", name="ck_idp_users_role_allowed"),
        sa.CheckConstraint("failed_attempts >= 0", name="ck_idp_users_failed_attempts_non_negative"),
    )
    # unique username (case-sensitive) + expression index for case-insensitive
    op.create_index("uq_idp_users_username", "idp_users", ["username"], unique=True)
    op.create_index("ix_idp_users_username_lower", "idp_users", [sa.text("lower(username)")], unique=True)
    op.create_index("uq_idp_users_email", "idp_users", ["email"], unique=True, postgresql_where=sa.text("email IS NOT NULL"))
    op.create_index("ix_idp_users_email_lower", "idp_users", [sa.text("lower(email)")], unique=True, postgresql_where=sa.text("email IS NOT NULL"))
    op.create_index("ix_idp_users_is_active", "idp_users", ["is_active"])
    op.create_index("ix_idp_users_deleted_at", "idp_users", ["deleted_at"])
    op.create_index("ix_idp_users_role", "idp_users", ["role"])


def downgrade():
    op.drop_index("ix_idp_users_role", table_name="idp_users")
    op.drop_index("ix_idp_users_deleted_at", table_name="idp_users")
    op.drop_index("ix_idp_users_is_active", table_name="idp_users")
    op.drop_index("ix_idp_users_email_lower", table_name="idp_users")
    op.drop_index("uq_idp_users_email", table_name="idp_users")
    op.drop_index("ix_idp_users_username_lower", table_name="idp_users")
    op.drop_index("uq_idp_users_username", table_name="idp_users")
    op.drop_table("idp_users")
