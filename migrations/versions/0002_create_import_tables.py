"""create secure import batch metadata"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_create_import_tables"
down_revision = "0001_create_identity_schema"

def upgrade():
    op.create_table("import_batches",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("parent_batch_id", sa.BigInteger(), sa.ForeignKey("import_batches.id")),
        sa.Column("root_batch_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("retry_reason", sa.String(80)), sa.Column("retry_depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("import_type", sa.String(40), nullable=False), sa.Column("input_profile", sa.String(60), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="received"), sa.Column("source_format", sa.String(10), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False), sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False), sa.Column("uploaded_by", sa.String(255), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("mapping_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("failed_at", sa.DateTime(timezone=True)), sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("uuid"), sa.CheckConstraint("source_format IN ('csv','xlsx')"))

def downgrade():
    op.drop_table("import_batches")