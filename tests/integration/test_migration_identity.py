import os

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
            assert columns["id"]["primary_key"]
            assert columns["uuid"]["nullable"] is False
            assert {"created_at", "updated_at"} <= columns.keys()
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
