"""add issuer to pegawai identity links

Revision ID: 0008_add_identity_link_issuer
Revises: 0007_add_outbox_event_deleted_at
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_add_identity_link_issuer"
down_revision = "0007_add_outbox_event_deleted_at"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pegawai_identity_links", sa.Column("issuer", sa.String(length=500), nullable=False, server_default=""))


def downgrade():
    op.drop_column("pegawai_identity_links", "issuer")
