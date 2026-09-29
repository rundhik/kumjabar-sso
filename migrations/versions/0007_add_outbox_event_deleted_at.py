"""add soft-delete column to outbox events

Revision ID: 0007_add_outbox_event_deleted_at
Revises: 0006_add_import_batch_deleted_at
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_add_outbox_event_deleted_at"
down_revision = "0006_add_import_batch_deleted_at"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("outbox_events", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_outbox_events_deleted_at", "outbox_events", ["deleted_at"])


def downgrade():
    op.drop_index("ix_outbox_events_deleted_at", table_name="outbox_events")
    op.drop_column("outbox_events", "deleted_at")
