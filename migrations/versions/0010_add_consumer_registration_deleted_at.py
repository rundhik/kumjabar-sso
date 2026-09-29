"""Add the soft-delete column required by ModelBase."""
from alembic import op
import sqlalchemy as sa

revision = "0010_add_consumer_registration_deleted_at"
down_revision = "0009_align_identity_link_lifecycle"


def upgrade():
    op.add_column(
        "consumer_registrations",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("consumer_registrations", "deleted_at")