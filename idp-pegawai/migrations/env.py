import logging
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Flask-Migrate: cuba pakai current_app bila ada, fallback ke config lama untuk test terisolasi.
config = context.config

if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except FileNotFoundError:
        # Saat file dipindah ke idp-pegawai/ (cwd=/usr/src/app), alembic.ini
        # berpindah dari migrations/alembic.ini ke alembic.ini. Toleransi.
        pass
    logger = logging.getLogger("alembic.env")


def _get_flask_engine_and_metadata():
    """Return (engine, metadata, url) dari Flask-Migrate bila app context ada."""
    from flask import current_app

    # Akan raise RuntimeError bila di luar app context — ditangkap caller.
    migrate_ext = current_app.extensions.get("migrate")
    if migrate_ext is None:
        raise RuntimeError("migrate extension not found")
    # Flask-SQLAlchemy >=3: db.engine ; <3: db.get_engine()
    try:
        engine = migrate_ext.db.get_engine()
    except (TypeError, AttributeError):
        engine = migrate_ext.db.engine
    # metadata untuk autogenerate
    if hasattr(migrate_ext.db, "metadatas"):
        metadata = migrate_ext.db.metadatas[None]
    else:
        metadata = migrate_ext.db.metadata
    try:
        url = engine.url.render_as_string(hide_password=False).replace("%", "%%")
    except AttributeError:
        url = str(engine.url).replace("%", "%%")
    return engine, metadata, url


# Tentukan sqlalchemy.url + target_metadata
# - Saat `flask db ...` : pakai engine/metadata dari Flask-Migrate
# - Saat `alembic` langsung (test isolation) : fallback ke DATABASE_URL / Config.build_db_uri
target_metadata = None
try:
    _engine, target_metadata, _url = _get_flask_engine_and_metadata()
    config.set_main_option("sqlalchemy.url", _url)
except Exception:
    # Fallback untuk `tests/integration/test_migration_identity.py` yang set
    # sqlalchemy.url via Config(tmp_path/alembic.ini) tanpa app context.
    # Runtime migrations must never target TEST_DATABASE_URL — itu hanya untuk test.
    from idp_pegawai.config import Config as _AppConfig

    _database_url = os.environ.get("DATABASE_URL") or _AppConfig.build_db_uri(
        _AppConfig.DB_DRIVER,
        _AppConfig.DB_USER,
        _AppConfig.DB_PASSWORD,
        _AppConfig.DB_HOST,
        _AppConfig.DB_PORT,
        _AppConfig.DB_NAME,
    )
    if _database_url:
        # Jangan overwrite bila test sudah set sqlalchemy.url secara eksplisit
        if not config.get_main_option("sqlalchemy.url"):
            config.set_main_option("sqlalchemy.url", _database_url)
    # target_metadata tetap None untuk mode fallback — migration script tetap jalan.


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # Coba Flask engine dulu; fallback ke engine_from_config untuk mode test
    connectable = None
    try:
        connectable, _, _ = _get_flask_engine_and_metadata()
        # _get_flask_engine_and_metadata memanggil current_app — pastikan context
        # masih valid. Bila gagal, fallback di bawah.
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
        return
    except Exception:
        pass

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
