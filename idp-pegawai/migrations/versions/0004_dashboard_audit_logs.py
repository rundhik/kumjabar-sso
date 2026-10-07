"""dashboard audit logs — keycloak_sync_logs + consumer_profile_request_logs

Revision ID: 0004_dashboard_audit_logs
Revises: 0003_create_idp_users
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_dashboard_audit_logs"
down_revision = "0003_create_idp_users"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "keycloak_sync_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("actor_user_id", sa.BigInteger(), sa.ForeignKey("idp_users.id"), nullable=True),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("detail", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_keycloak_sync_logs_created_at", "keycloak_sync_logs", ["created_at"])

    op.create_table(
        "consumer_profile_request_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("consumer_id", sa.String(255), nullable=False),
        sa.Column("endpoint", sa.String(500), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("pegawai_uuid", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_consumer_profile_request_logs_requested_at", "consumer_profile_request_logs", ["requested_at"])
    op.create_index("ix_consumer_profile_request_logs_consumer_id", "consumer_profile_request_logs", ["consumer_id"])

def downgrade():
    op.drop_index("ix_consumer_profile_request_logs_consumer_id", table_name="consumer_profile_request_logs")
    op.drop_index("ix_consumer_profile_request_logs_requested_at", table_name="consumer_profile_request_logs")
    op.drop_table("consumer_profile_request_logs")
    op.drop_index("ix_keycloak_sync_logs_created_at", table_name="keycloak_sync_logs")
    op.drop_table("keycloak_sync_logs")
