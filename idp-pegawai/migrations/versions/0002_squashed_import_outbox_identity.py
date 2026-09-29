"""create import, outbox and identity link lifecycle — squashed additive patches

Revision ID: 0002_squashed_import_outbox_identity
Revises: 0001_create_identity_schema
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_squashed_import_outbox_identity"
down_revision = "0001_create_identity_schema"
branch_labels = None
depends_on = None


def upgrade():
    # import_batches — sudah include deleted_at (gabungan 0002 + 0006)
    op.create_table(
        "import_batches",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("parent_batch_id", sa.BigInteger(), sa.ForeignKey("import_batches.id")),
        sa.Column("root_batch_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("retry_reason", sa.String(80)),
        sa.Column("retry_depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("import_type", sa.String(40), nullable=False),
        sa.Column("input_profile", sa.String(60), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="received"),
        sa.Column("source_format", sa.String(10), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False),
        sa.Column("uploaded_by", sa.String(255), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("mapping_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("uuid"),
        sa.CheckConstraint("source_format IN ('csv','xlsx')"),
    )

    # outbox_events — sudah include deleted_at (gabungan 0003 + 0007)
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("aggregate_type", sa.String(80), nullable=False, server_default="import_batch"),
        sa.Column("aggregate_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("uuid"),
    )
    op.create_index("ix_outbox_events_deleted_at", "outbox_events", ["deleted_at"])

    # outbox_consumer_deliveries — dari 0004 (tetap, dipakai delivery.py)
    op.create_table(
        "outbox_consumer_deliveries",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("outbox_event_id", sa.BigInteger(), sa.ForeignKey("outbox_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consumer_code", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("dispatch_attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_dispatch_at", sa.DateTime(timezone=True)),
        sa.Column("lease_owner", sa.String(255)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("lease_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(100)),
        sa.Column("last_error_at", sa.DateTime(timezone=True)),
        sa.Column("dispatched_job_id", postgresql.UUID(as_uuid=True)),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("uuid"),
        sa.UniqueConstraint("outbox_event_id", "consumer_code", name="uq_outbox_consumer_deliveries_event_consumer"),
        sa.CheckConstraint("status IN ('pending','claiming','dispatched','retry_wait','blocked','dead_letter')", name="ck_outbox_consumer_deliveries_status"),
    )
    op.create_index("uq_outbox_consumer_deliveries_dispatched_job_id", "outbox_consumer_deliveries", ["dispatched_job_id"], unique=True, postgresql_where=sa.text("dispatched_job_id IS NOT NULL"))

    # pegawai_identity_links lifecycle — gabungan 0008 + 0009 (issuer + lifecycle columns)
    # 0001 sudah bikin tabel dasar; tambahkan kolom yang dulunya patch terpisah
    op.add_column("pegawai_identity_links", sa.Column("issuer", sa.String(length=500), nullable=False, server_default=""))
    op.add_column("pegawai_identity_links", sa.Column("management_mode", sa.String(length=30), nullable=False, server_default="idp_managed"))
    op.add_column("pegawai_identity_links", sa.Column("link_status", sa.String(length=30), nullable=False, server_default="reserved"))
    op.add_column("pegawai_identity_links", sa.Column("link_version", sa.BigInteger(), nullable=False, server_default="1"))
    op.add_column("pegawai_identity_links", sa.Column("correlation_uuid", sa.Uuid(), nullable=True))
    op.add_column("pegawai_identity_links", sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("pegawai_identity_links", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    for column in ("deleted_at", "unlinked_at", "correlation_uuid", "link_version", "link_status", "management_mode", "issuer"):
        op.drop_column("pegawai_identity_links", column)
    op.drop_index("uq_outbox_consumer_deliveries_dispatched_job_id", table_name="outbox_consumer_deliveries")
    op.drop_table("outbox_consumer_deliveries")
    op.drop_index("ix_outbox_events_deleted_at", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_table("import_batches")
