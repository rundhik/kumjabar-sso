from pathlib import Path

from .models.base import Base, db
from flask_migrate import Migrate

# Flask-Migrate directory eksplisit: idp-pegawai/migrations (bukan migrations/alembic.ini relatif)
# Pakai absolute path agar tahan terhadap perubahan cwd (docker: /usr/src/app vs /usr/src/app/idp-pegawai)
_MIGRATIONS_DIR = str(Path(__file__).resolve().parent / "migrations")
migrate = Migrate(directory=_MIGRATIONS_DIR)

__all__ = ["Base", "db", "migrate"]
