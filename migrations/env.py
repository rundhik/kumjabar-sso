from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from idp_pegawai.config import Config
import os

config = context.config
# Runtime migrations must never target TEST_DATABASE_URL. That variable is
# reserved for explicitly isolated migration tests because those tests perform
# destructive downgrade-to-base cleanup.
database_url = (
    os.environ.get("DATABASE_URL")
    or Config.build_db_uri(
        Config.DB_DRIVER,
        Config.DB_USER,
        Config.DB_PASSWORD,
        Config.DB_HOST,
        Config.DB_PORT,
        Config.DB_NAME,
    )
)
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)
if config.config_file_name:
    import os
    if os.path.exists(config.config_file_name):
        fileConfig(config.config_file_name)

def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction(): context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction(): context.run_migrations()

(run_migrations_offline if context.is_offline_mode() else run_migrations_online)()
