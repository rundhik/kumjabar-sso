"""create identity schema

Revision ID: 0001_create_identity_schema
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_create_identity_schema"
down_revision = None


def _common():
    return [sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True), sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")), sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))]


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table("org_units", *_common(), sa.Column("parent_id", sa.BigInteger(), nullable=True), sa.Column("code", sa.String(80), nullable=False), sa.Column("slug", sa.String(120), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("short_name", sa.String(120)), sa.Column("unit_type", sa.String(40), nullable=False), sa.Column("level", sa.Integer(), nullable=False), sa.Column("path", sa.String(500), nullable=False), sa.Column("keycloak_group_path", sa.String(500), nullable=False), sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("effective_from", sa.Date()), sa.Column("effective_to", sa.Date()), sa.Column("deleted_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["parent_id"], ["org_units.id"], name="fk_org_units_parent_id_org_units"), sa.UniqueConstraint("uuid", name="uq_org_units_uuid"), sa.CheckConstraint("unit_type IN ('kanwil','divisi','bidang','bagian','pokja','tim')", name="ck_org_units_unit_type_allowed"), sa.CheckConstraint("level >= 0", name="ck_org_units_level_non_negative"), sa.CheckConstraint("path LIKE '/%'", name="ck_org_units_path_absolute"), sa.CheckConstraint("keycloak_group_path LIKE '/pegawai/%'", name="ck_org_units_keycloak_group_path_employee"), sa.CheckConstraint("effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from", name="ck_org_units_effective_range"))
    op.create_table("pegawai", *_common(), sa.Column("nip", sa.String(18), nullable=False), sa.Column("nama_lengkap", sa.String(255), nullable=False), sa.Column("gelar_depan", sa.String(80)), sa.Column("gelar_belakang", sa.String(120)), sa.Column("email_dinas", sa.String(255)), sa.Column("email_dinas_normalized", sa.String(255)), sa.Column("email_google", sa.String(255)), sa.Column("email_google_normalized", sa.String(255)), sa.Column("no_hp", sa.String(50)), sa.Column("primary_org_unit_id", sa.BigInteger()), sa.Column("status_pegawai", sa.String(40), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("status_reason", sa.Text()), sa.Column("status_effective_at", sa.Date()), sa.Column("keycloak_user_id", sa.String(120)), sa.Column("deleted_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["primary_org_unit_id"], ["org_units.id"], name="fk_pegawai_primary_org_unit_id_org_units"), sa.UniqueConstraint("uuid", name="uq_pegawai_uuid"), sa.CheckConstraint("nip ~ '^[0-9]{18}$'", name="ck_pegawai_nip_18_digits"), sa.CheckConstraint("status_pegawai IN ('aktif','mutasi_keluar','pensiun','nonaktif','meninggal')", name="ck_pegawai_status_allowed"), sa.CheckConstraint("is_active = (status_pegawai = 'aktif')", name="ck_pegawai_active_status_consistency"), sa.CheckConstraint("is_active = false OR primary_org_unit_id IS NOT NULL", name="ck_pegawai_active_requires_primary_org_unit"))
    op.create_table("pegawai_org_assignments", *_common(), sa.Column("pegawai_id", sa.BigInteger(), nullable=False), sa.Column("org_unit_id", sa.BigInteger(), nullable=False), sa.Column("assignment_type", sa.String(40), nullable=False), sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("started_at", sa.Date()), sa.Column("ended_at", sa.Date()), sa.Column("deleted_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["pegawai_id"], ["pegawai.id"], name="fk_pegawai_org_assignments_pegawai_id_pegawai"), sa.ForeignKeyConstraint(["org_unit_id"], ["org_units.id"], name="fk_pegawai_org_assignments_org_unit_id_org_units"), sa.UniqueConstraint("uuid", name="uq_pegawai_org_assignments_uuid"), sa.CheckConstraint("assignment_type IN ('primary','additional')", name="ck_pegawai_org_assignments_assignment_type_allowed"), sa.CheckConstraint("ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at", name="ck_pegawai_org_assignments_date_range"), sa.CheckConstraint("is_primary = false OR assignment_type = 'primary'", name="ck_pegawai_org_assignments_primary_type_consistency"))
    op.create_table("pegawai_identity_links", *_common(), sa.Column("pegawai_id", sa.BigInteger(), nullable=False), sa.Column("provider", sa.String(40), nullable=False), sa.Column("provider_subject", sa.String(255)), sa.Column("email", sa.String(255)), sa.Column("email_normalized", sa.String(255)), sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("linked_at", sa.DateTime(timezone=True)), sa.Column("last_seen_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["pegawai_id"], ["pegawai.id"], name="fk_pegawai_identity_links_pegawai_id_pegawai"), sa.UniqueConstraint("uuid", name="uq_pegawai_identity_links_uuid"), sa.CheckConstraint("provider IN ('keycloak','google','microsoft','local')", name="ck_pegawai_identity_links_provider_allowed"))
    indexes = {
        "org_units": ["parent_id", "unit_type", "is_active", "level", "sort_order"],
        "pegawai": ["primary_org_unit_id", "status_pegawai", "is_active", "keycloak_user_id", "email_dinas_normalized", "email_google_normalized"],
        "pegawai_org_assignments": ["pegawai_id", "org_unit_id", "assignment_type", "is_active"],
        "pegawai_identity_links": ["pegawai_id", "provider", "email_normalized", "is_active"],
    }
    for table, cols in indexes.items():
        for col in cols:
            op.create_index(f"ix_{table}_{col}", table, [col])
    op.create_index("uq_org_units_code_active", "org_units", ["code"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("uq_org_units_path_active", "org_units", ["path"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("uq_org_units_keycloak_group_path_active", "org_units", ["keycloak_group_path"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("uq_pegawai_nip_active", "pegawai", ["nip"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    for name, col in (("uq_pegawai_email_dinas_active", "email_dinas_normalized"), ("uq_pegawai_email_google_active", "email_google_normalized"), ("uq_pegawai_keycloak_user_id_active", "keycloak_user_id")):
        op.create_index(name, "pegawai", [col], unique=True, postgresql_where=sa.text(f"{col} IS NOT NULL AND deleted_at IS NULL"))
    op.create_index("uq_pegawai_org_assignments_active_primary_per_pegawai", "pegawai_org_assignments", ["pegawai_id"], unique=True, postgresql_where=sa.text("is_primary = true AND is_active = true AND deleted_at IS NULL"))
    op.create_index("uq_pegawai_org_assignments_active_same", "pegawai_org_assignments", ["pegawai_id", "org_unit_id", "assignment_type"], unique=True, postgresql_where=sa.text("is_active = true AND deleted_at IS NULL"))
    op.create_index("uq_pegawai_identity_links_provider_subject", "pegawai_identity_links", ["provider", "provider_subject"], unique=True, postgresql_where=sa.text("provider_subject IS NOT NULL"))


def downgrade():
    # The upgrade uses these dynamic names; keep their templates explicit for review.
    # "ix_{table}_{col}" and the loop's table name "pegawai" expand to the
    # concrete indexes listed below.
    # Drop indexes before their tables, in reverse dependency-safe order.
    for name, table in (
        ("uq_pegawai_identity_links_provider_subject", "pegawai_identity_links"),
        ("ix_pegawai_identity_links_is_active", "pegawai_identity_links"),
        ("ix_pegawai_identity_links_email_normalized", "pegawai_identity_links"),
        ("ix_pegawai_identity_links_provider", "pegawai_identity_links"),
        ("ix_pegawai_identity_links_pegawai_id", "pegawai_identity_links"),
        ("uq_pegawai_org_assignments_active_same", "pegawai_org_assignments"),
        ("uq_pegawai_org_assignments_active_primary_per_pegawai", "pegawai_org_assignments"),
        ("ix_pegawai_org_assignments_is_active", "pegawai_org_assignments"),
        ("ix_pegawai_org_assignments_assignment_type", "pegawai_org_assignments"),
        ("ix_pegawai_org_assignments_org_unit_id", "pegawai_org_assignments"),
        ("ix_pegawai_org_assignments_pegawai_id", "pegawai_org_assignments"),
        ("uq_pegawai_keycloak_user_id_active", "pegawai"),
        ("uq_pegawai_email_google_active", "pegawai"),
        ("uq_pegawai_email_dinas_active", "pegawai"),
        ("uq_pegawai_nip_active", "pegawai"),
        ("ix_pegawai_nip", "pegawai"),
        ("ix_pegawai_email_google_normalized", "pegawai"),
        ("ix_pegawai_email_dinas_normalized", "pegawai"),
        ("ix_pegawai_keycloak_user_id", "pegawai"),
        ("ix_pegawai_is_active", "pegawai"),
        ("ix_pegawai_status_pegawai", "pegawai"),
        ("ix_pegawai_primary_org_unit_id", "pegawai"),
        ("uq_org_units_keycloak_group_path_active", "org_units"),
        ("uq_org_units_path_active", "org_units"),
        ("uq_org_units_code_active", "org_units"),
        ("ix_org_units_sort_order", "org_units"),
        ("ix_org_units_level", "org_units"),
        ("ix_org_units_is_active", "org_units"),
        ("ix_org_units_unit_type", "org_units"),
        ("ix_org_units_parent_id", "org_units"),
    ):
        op.drop_index(name, table_name=table)
    for table in ("pegawai_identity_links", "pegawai_org_assignments", "pegawai", "org_units"):
        op.drop_table(table)
