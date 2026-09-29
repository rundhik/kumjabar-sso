"""align identity link lifecycle columns with current model

Revision ID: 0009_align_identity_link_lifecycle
Revises: 0008_add_identity_link_issuer
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_align_identity_link_lifecycle"
down_revision = "0008_add_identity_link_issuer"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "pegawai_identity_links",
        sa.Column("management_mode", sa.String(length=30), nullable=False, server_default="idp_managed"),
    )
    op.add_column(
        "pegawai_identity_links",
        sa.Column("link_status", sa.String(length=30), nullable=False, server_default="reserved"),
    )
    op.add_column(
        "pegawai_identity_links",
        sa.Column("link_version", sa.BigInteger(), nullable=False, server_default="1"),
    )
    op.add_column(
        "pegawai_identity_links",
        sa.Column("correlation_uuid", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "pegawai_identity_links",
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "pegawai_identity_links",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    for column in ("deleted_at", "unlinked_at", "correlation_uuid", "link_version", "link_status", "management_mode"):
        op.drop_column("pegawai_identity_links", column)
