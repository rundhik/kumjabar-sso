from pathlib import Path
from flask_migrate import Migrate
from .models.base import Base, db

# Migrations live at service root idp-pegawai/migrations (like dasborkanwil/migrations at repo root)
_MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")
migrate = Migrate(directory=_MIGRATIONS_DIR)

__all__ = ["Base", "db", "migrate"]
