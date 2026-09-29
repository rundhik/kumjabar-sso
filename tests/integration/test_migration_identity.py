import os
from urllib.parse import urlsplit

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text


@pytest.mark.integration
@pytest.mark.postgresql
def test_identity_migration_schema_and_downgrade(tmp_path):
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL belum dikonfigurasi")
    runtime_url = os.getenv("DATABASE_URL")
    if not runtime_url:
        from idp_pegawai.config import Config as AppConfig
        runtime_url = AppConfig.build_db_uri(AppConfig.DB_DRIVER, AppConfig.DB_USER, AppConfig.DB_PASSWORD, AppConfig.DB_HOST, AppConfig.DB_PORT, AppConfig.DB_NAME)
    if database_url == runtime_url:
        pytest.fail("TEST_DATABASE_URL wajib menunjuk database terisolasi, bukan DATABASE_URL runtime")

    config = Config(str(tmp_path / "alembic.ini"))
    config.set_main_option("script_location", "migrations")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    from sqlalchemy import create_engine
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert {"org_units", "pegawai", "pegawai_org_assignments", "pegawai_identity_links"} <= set(inspector.get_table_names())
        for table in ("org_units", "pegawai", "pegawai_org_assignments", "pegawai_identity_links"):
            columns = {c["name"]: c for c in inspector.get_columns(table)}
            assert "id" in inspector.get_pk_constraint(table)["constrained_columns"]
            assert columns["uuid"]["nullable"] is False
            assert {"created_at", "updated_at"} <= columns.keys()
        assert "deleted_at" in {c["name"] for c in inspector.get_columns("org_units")}
        assert "deleted_at" in {c["name"] for c in inspector.get_columns("pegawai")}
        assert "deleted_at" in {c["name"] for c in inspector.get_columns("pegawai_org_assignments")}
        index_names = {
            table: {index["name"] for index in inspector.get_indexes(table)}
            for table in ("org_units", "pegawai", "pegawai_org_assignments", "pegawai_identity_links")
        }
        assert {"uq_org_units_code_active", "uq_org_units_path_active", "uq_org_units_keycloak_group_path_active"} <= index_names["org_units"]
        assert {"uq_pegawai_nip_active", "uq_pegawai_email_dinas_active", "uq_pegawai_email_google_active", "uq_pegawai_keycloak_user_id_active"} <= index_names["pegawai"]
        assert {"uq_pegawai_org_assignments_active_primary_per_pegawai", "uq_pegawai_org_assignments_active_same"} <= index_names["pegawai_org_assignments"]
        assert "uq_pegawai_identity_links_provider_subject" in index_names["pegawai_identity_links"]
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO org_units (code, slug, name, unit_type, level, path, keycloak_group_path) VALUES ('T', 't', 'T', 'kanwil', 0, '/t', '/pegawai/t')"))
            unit_id = conn.execute(text("SELECT id FROM org_units WHERE code='T'")).scalar_one()
            conn.execute(text("INSERT INTO pegawai (nip, nama_lengkap, status_pegawai, is_active, primary_org_unit_id) VALUES ('123456789012345678', 'Test', 'aktif', true, :id)"), {"id": unit_id})
            with pytest.raises(Exception):
                conn.execute(text("INSERT INTO pegawai (nip, nama_lengkap, status_pegawai, is_active, primary_org_unit_id) VALUES ('12345678901234567X', 'Bad', 'aktif', true, :id)"), {"id": unit_id})
    finally:
        command.downgrade(config, "base")
        engine.dispose()
        assert not inspect(create_engine(database_url)).has_table("pegawai")
