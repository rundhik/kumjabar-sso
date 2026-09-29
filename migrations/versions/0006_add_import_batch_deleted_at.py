"""add soft-delete column to import batches"""
from alembic import op
import sqlalchemy as sa

revision = "0006_add_import_batch_deleted_at"
down_revision = "0005_create_consumer_registration_change_log"


def upgrade():
    op.add_column("import_batches", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("import_batches", "deleted_at")
