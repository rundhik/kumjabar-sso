"""create transactional outbox events"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0003_create_outbox_events"
down_revision = "0002_create_import_tables"
def upgrade():
    op.create_table("outbox_events", sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True), sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")), sa.Column("event_type", sa.String(80), nullable=False), sa.Column("aggregate_type", sa.String(80), nullable=False, server_default="import_batch"), sa.Column("aggregate_uuid", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("provenance", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("status", sa.String(20), nullable=False, server_default="pending"), sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.UniqueConstraint("uuid"))
def downgrade():
    op.drop_table("outbox_events")