"""create durable per-consumer outbox delivery state"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_create_outbox_consumer_deliveries"
down_revision = "0003_create_outbox_events"


def upgrade():
    op.create_table(
        "outbox_consumer_deliveries",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("outbox_event_id", sa.BigInteger(), sa.ForeignKey("outbox_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consumer_code", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("dispatch_attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_dispatch_at", sa.DateTime(timezone=True)), sa.Column("lease_owner", sa.String(255)),
        sa.Column("lease_until", sa.DateTime(timezone=True)), sa.Column("lease_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(100)), sa.Column("last_error_at", sa.DateTime(timezone=True)),
        sa.Column("dispatched_job_id", postgresql.UUID(as_uuid=True)), sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("uuid"), sa.UniqueConstraint("outbox_event_id", "consumer_code", name="uq_outbox_consumer_deliveries_event_consumer"),
        sa.CheckConstraint("status IN ('pending','claiming','dispatched','retry_wait','blocked','dead_letter')", name="ck_outbox_consumer_deliveries_status"),
    )
    op.create_index("uq_outbox_consumer_deliveries_dispatched_job_id", "outbox_consumer_deliveries", ["dispatched_job_id"], unique=True, postgresql_where=sa.text("dispatched_job_id IS NOT NULL"))


def downgrade():
    op.drop_index("uq_outbox_consumer_deliveries_dispatched_job_id", table_name="outbox_consumer_deliveries")
    op.drop_table("outbox_consumer_deliveries")