# IDP Pegawai — Rapikan ke Flask-Migrate (Tanpa Tercecer di Root) Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Merapikan `idp-pegawai` agar migration dikelola via **Flask-Migrate** (bukan Alembic CLI tercecer di root), konsolidasi duplikasi `src/` vs `idp-pegawai/`, dan menjaga history 10 migrasi + alur SSO/token-exchange tetap hijau.

**Architecture:** `Flask-Migrate` membungkus Alembic dan di-init dari `create_app()` via `Migrate(app, db)`; `migrations/env.py` dijalankan dalam application context sehingga `target_metadata = db.metadata` dan autogenerate akurat; `migrations/` tetap satu lokasi tapi di-drive oleh `flask db`; duplikasi `db` di `extensions.py` vs `models/base.py` disatukan; `docker-compose` dan `alembic.ini` disesuaikan agar tidak mengandalkan `TEST_DATABASE_URL` di runtime.

**Tech Stack:** Python 3.11, Flask 3.1, Flask-SQLAlchemy 3.1, Flask-Migrate (Alembic 1.13), psycopg[binary], PostgreSQL `global_postgresql` / `db_sso`, pytest.

---

## 0. Konteks & Asumsi (hasil audit 2026-09-29)

### Struktur saat ini
- Root memiliki `alembic.ini` (`script_location = %(here)s/migrations`, `prepend_sys_path = %(here)s/src`) dan `migrations/` (10 versi `0001..0010`) — terkesan tercecer di root.
- Package utama adalah folder **`idp-pegawai/`** (flat layout) dengan shim `idp-pegawai/idp_pegawai.py` yang me-load `idp-pegawai/__init__.py` sebagai package `idp_pegawai`.
- `pyproject.toml`: `pythonpath = ["idp-pegawai"]`, `packages.find.where = ["idp-pegawai"]`.
- Duplikasi `db`:
  - `idp-pegawai/extensions.py` → `db = SQLAlchemy()` (tanpa `model_class`)
  - `idp-pegawai/models/base.py` → `db = SQLAlchemy(model_class=Base)` (dengan `Base`, `ModelBase`, mixins)
- `src/idp_pegawai/` ada tapi **sebagian besar kosong** (hanya `__pycache__`, beberapa template, `operations/readiness.py`); `git ls-files | grep ^src` hanya melacak sedikit file — sumber kebenaran ada di `idp-pegawai/`.
- `migrations/env.py` saat ini `target_metadata=None` dan membangun URL dari `Config.build_db_uri()` + `DATABASE_URL`; `alembic.ini` tidak punya `sqlalchemy.url` default.
- `idp-pegawai/docker-compose.yml` menjalankan `alembic upgrade head && flask --app 'idp_pegawai:create_app()' run` dengan `PYTHONPATH=/usr/src/app/idp-pegawai`.
- SSO/Keycloak + token exchange `s1-jabar` sudah jalan — jangan ubah claim/issuer/audience/JWKS.

### Kontrak yang wajib dijaga
- 10 migrasi existing harus tetap valid dan reversible (test `test_identity_migration_downgrade_drops_every_created_index` + `test_migration_identity` isolated).
- `Flask-Migrate` tidak boleh mereset `alembic_version` atau mengganti `version_num VARCHAR(32)` → `VARCHAR(128)` yang sudah di-migrate di `0001`.
- `TEST_DATABASE_URL` tetap isolasi: tidak boleh dipakai runtime; hanya untuk test integrasi yang `downgrade base`.
- External Docker network `project_network` + `global_postgresql` tetap sumber kebenaran (jangan ganti ke SQLite).
- `AGENTS.md` tetap berlaku: factory tipis modular, layer models/repositories/services/routes.

### Referensi dasborkanwil
- Router memblokir baca `/home/user/projects/dasborkanwil` bahkan setelah izin read-only — plan ini memakai best-practice Flask-Migrate yang setara (pola `extensions.db + migrate`, `migrate.init_app(app, db)`, `flask db` CLI, `env.py` pakai `current_app + target_metadata`).

---

## 1. Strategi

1. **Tambah Flask-Migrate sebagai dependency** — jangan hapus Alembic.
2. **Satukan `db` single-source** di `extensions.py` (pakai `model_class=Base`) dan jadikan `models/base.py` re-export agar import lama tetap jalan.
3. **Wire `Migrate` di factory** — `migrate.init_app(app, db)` setelah `db.init_app(app)`.
4. **Rapikan `migrations/env.py`** ke pola Flask-Migrate (pakai `current_app`, `target_metadata=db.metadata`, tetap hormati `DATABASE_URL` non-destruktif, jangan pakai `TEST_DATABASE_URL`).
5. **Rapikan `alembic.ini`** — hilangkan `prepend_sys_path` ke `src` yang salah, set `script_location` tetap `migrations` atau `idp-pegawai/migrations` sesuai keputusan (opsi A di bawah).
6. **Rapikan `pyproject.toml` + `alembic.ini` + `docker-compose.yml`** agar `flask db upgrade` jadi entrypoint, bukan `alembic upgrade head`.
7. **Konsolidasi `src/` vs `idp-pegawai/`** — putuskan satu source of truth (`idp-pegawai/`) dan jadikan `src/` shim atau kosongkan agar tidak drift.
8. **Verifikasi** dengan `pytest` dan `flask db current/upgrade/downgrade` di container `python3-base:latest` + `global_postgresql`.

### Keputusan lokasi `migrations/` (pilih satu, default: Opsi A)

- **Opsi A — Tetap di root `migrations/`** (paling aman, tidak memindahkan history git): `migrations/` tetap di root tapi di-drive via `flask db` (Flask-Migrate default `migrations`). Cocok karena 10 file sudah di-track di `migrations/versions/`.
- **Opsi B — Pindah ke `idp-pegawai/migrations/`**: lebih rapi secara domain tapi butuh `git mv` + update `alembic.ini` + `Migrate(directory=...)` + rewrite path di test. Hanya lakukan jika user minta eksplisit.

Plan ini memakai **Opsi A** (tidak memindahkan folder) agar “tidak tercecer” diartikan sebagai “tidak dipanggil manual via `alembic` di root, tapi via `flask db` yang terikat app” + `alembic.ini` dirapikan. Jika user ingin fisik pindah, ada task opsional di akhir.

---

## 2. Step-by-step Plan (TDD, commit kecil)

### Task 0: Baseline & guard — buktikan kondisi sebelum ubahan

**Objective:** Catat baseline agar regresi terdeteksi.

**Files:**
- Read: `pyproject.toml`, `alembic.ini`, `migrations/env.py`, `idp-pegawai/extensions.py`, `idp-pegawai/models/base.py`, `idp-pegawai/__init__.py`, `tests/conftest.py`

**Step 1:** Jalankan
```bash
pytest tests/unit/test_migration_definition.py tests/integration/test_migration_identity.py -q
pytest -q  # expect 2 skipped jika TEST_DATABASE_URL kosong, lainnya pass
alembic current 2>&1 | head -n 20
```
Expected: `test_identity_migration_downgrade_drops_every_created_index` PASS; integration SKIP bila `TEST_DATABASE_URL` kosong.

**Step 2:** Commit baseline log (tidak ubah kode) — cukup catat di plan execution log.

---

### Task 1: Tambah Flask-Migrate ke dependencies

**Objective:** Menjadikan `flask db` tersedia tanpa menghapus Alembic.

**Files:**
- Modify: `pyproject.toml:10`

**Step 1 — Edit `pyproject.toml`:**
```toml
dependencies = ["Flask>=3.0,<4.0", "Flask-SQLAlchemy>=3.1,<4.0", "Flask-Migrate>=4.0,<5.0", "Alembic>=1.13,<2.0", "psycopg[binary]>=3.1,<4.0", "python-dotenv>=1.0,<2.0", "PyJWT[crypto]>=2.8,<3.0"]
```

**Step 2 — Verifikasi:**
```bash
pip install -e ".[test]"  # di .venv atau container python3-base:latest
flask --help | grep -q "db" && echo "flask db found" || flask db --help
```
Expected: `flask db` muncul.

**Step 3 — Commit:**
```bash
git add pyproject.toml
git commit -m "chore: add Flask-Migrate dependency for idp-pegawai"
```

---

### Task 2: Satukan `db` single-source di `extensions.py`

**Objective:** Hilangkan duplikasi `SQLAlchemy()` agar `Migrate` dan models pakai 1 `db.metadata`.

**Files:**
- Modify: `idp-pegawai/extensions.py`
- Modify: `idp-pegawai/models/base.py` (jadi re-export)

**Step 1 — Tulis `idp-pegawai/extensions.py` menjadi single source:**
```python
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone
from uuid import uuid4, UUID
from sqlalchemy import BigInteger, DateTime, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

class FlexibleUUID(TypeDecorator):
    impl = Uuid
    cache_ok = True
    def process_bind_param(self, value, dialect):
        if value is None or isinstance(value, UUID):
            return value
        return UUID(str(value))
    def process_result_value(self, value, dialect):
        return value

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Re-export mixins agar import lama tetap jalan jika ada yang import dari extensions
__all__ = ["db", "Base"]
```
> Catatan: alternatif yang lebih minimal — biarkan `models/base.py` tetap definisikan `Base`/mixins lalu `extensions.py` import dari sana. Pilih salah satu, jangan duplikasi definisi `Base`. Opsi yang disarankan: definisi `Base` + `db` tetap di `models/base.py`, lalu `extensions.py` jadi shim `from .models.base import db, Base`. Ini paling kecil diff-nya.

**Opsi B (lebih kecil diff, direkomendasikan):**
```python
# idp-pegawai/extensions.py
from .models.base import db, Base  # re-export single source
__all__ = ["db", "Base"]
```

**Step 2 — Sesuaikan `idp-pegawai/models/base.py` agar tidak membuat `db` kedua:**
- Jika pakai Opsi B, `models/base.py` tetap `db = SQLAlchemy(model_class=Base)` dan `extensions.py` hanya re-export.
- Pastikan `ModelBase` tetap ada dan `__all__` tetap expose `db`.

**Step 3 — Verifikasi:**
```bash
python -c "from idp_pegawai.extensions import db; from idp_pegawai.models.base import db as db2; assert db is db2; print('db single source OK')"
pytest tests/unit/test_migration_definition.py -q
```
Expected: PASS.

**Step 4 — Commit:**
```bash
git add idp-pegawai/extensions.py idp-pegawai/models/base.py
git commit -m "refactor: single-source db for Flask-Migrate (extensions re-export base)"
```

---

### Task 3: Wire Flask-Migrate di application factory

**Objective:** `create_app()` menginisialisasi `Migrate`.

**Files:**
- Modify: `idp-pegawai/__init__.py:1-72`

**Step 1 — Edit `idp-pegawai/__init__.py`:**
```python
from .extensions import db, migrate  # atau from flask_migrate import Migrate jika belum di extensions
# ...
def create_app(config_object=None):
    # ... existing db.init_app(app), init_security(app)
    from .extensions import migrate
    migrate.init_app(app, db)
    # ... repositories, blueprints
    return app
```
Jika `migrate` didefinisikan di `extensions.py`:
```python
# extensions.py
from flask_migrate import Migrate
migrate = Migrate()
```

**Step 2 — Verifikasi:**
```bash
python -c "from idp_pegawai import create_app; app=create_app({'TESTING':True}); print(list(app.extensions.keys()))" | grep -q migrate
flask --app 'idp_pegawai:create_app()' db --help | head -n 20
```
Expected: `migrate` ada di `app.extensions`; `flask db` commands muncul.

**Step 3 — Commit:**
```bash
git add idp-pegawai/__init__.py idp-pegawai/extensions.py
git commit -m "feat: wire Flask-Migrate in create_app"
```

---

### Task 4: Rapikan `migrations/env.py` ke pola Flask-Migrate

**Objective:** `env.py` pakai `current_app` + `target_metadata` agar `flask db migrate` akurat dan tidak butuh `sqlalchemy.url` manual.

**Files:**
- Modify: `migrations/env.py`

**Step 1 — Ganti `migrations/env.py` (contoh Flask-Migrate standard, sesuaikan dengan guard TEST_DATABASE_URL):**
```python
import logging
from logging.config import fileConfig
from flask import current_app
from alembic import context

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
    logger = logging.getLogger('alembic.env')

def get_engine():
    try:
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError, KeyError):
        return current_app.extensions['migrate'].db.engine

def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace('%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')

def get_metadata():
    if hasattr(current_app.extensions['migrate'].db, 'metadatas'):
        return current_app.extensions['migrate'].db.metadatas[None]
    return current_app.extensions['migrate'].db.metadata

config.set_main_option('sqlalchemy.url', get_engine_url())
target_metadata = get_metadata()

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = get_engine()
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```
Pertahankan guard: jangan pernah pakai `TEST_DATABASE_URL` di runtime; `TEST_DATABASE_URL` hanya dipakai oleh test yang bikin `Config` terisolasi.

**Step 2 — Verifikasi:**
```bash
pytest tests/unit/test_migration_definition.py -q
python -c "from idp_pegawai import create_app; app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:'}); ctx=app.app_context(); ctx.push(); from alembic.config import Config; c=Config('migrations/env.py'); print('env ok'); ctx.pop()"
```
Expected: tidak error import; test tetap PASS.

**Step 3 — Commit:**
```bash
git add migrations/env.py
git commit -m "refactor: migrations env uses Flask-Migrate app context and target_metadata"
```

---

### Task 5: Rapikan `alembic.ini`

**Objective:** Hilangkan `prepend_sys_path = %(here)s/src` yang salah (pythonpath adalah `idp-pegawai`), dan biarkan Flask-Migrate yang set URL.

**Files:**
- Modify: `alembic.ini`

**Step 1 — Edit `alembic.ini`:**
```ini
[alembic]
script_location = migrations
# prepend_sys_path dihapus atau di-set ke idp-pegawai jika masih butuh
# prepend_sys_path = %(here)s/idp-pegawai
sqlalchemy.url =

[loggers]
...
```
Jika tetap butuh `prepend_sys_path` untuk compat, ganti ke `%(here)s/idp-pegawai`.

**Step 2 — Verifikasi:**
```bash
cat alembic.ini
flask --app 'idp_pegawai:create_app()' db current 2>&1 | head -n 20
```
Expected: `alembic.ini` tidak lagi menunjuk `src`.

**Step 3 — Commit:**
```bash
git add alembic.ini
git commit -m "chore: fix alembic.ini script_location and prepend_sys_path for Flask-Migrate"
```

---

### Task 6: Rapikan `pyproject.toml` pythonpath & packages

**Objective:** Pastikan `pytest` dan `flask` konsisten import `idp_pegawai` dari `idp-pegawai/`.

**Files:**
- Modify: `pyproject.toml:16-25`

**Step 1 — Pastikan tetap:**
```toml
[tool.pytest.ini_options]
pythonpath = ["idp-pegawai"]
[tool.setuptools.packages.find]
where = ["idp-pegawai"]
```
Jika ingin lebih eksplisit untuk Flask-Migrate, tambah `FLASK_APP` di `.env.example`:
```
FLASK_APP=idp_pegawai:create_app()
```

**Step 2 — Verifikasi:**
```bash
pytest tests/conftest.py -q
python -c "import idp_pegawai; print(idp_pegawai.__file__)"
```
Expected: import dari `idp-pegawai/`.

**Step 3 — Commit (jika ada perubahan):**
```bash
git add pyproject.toml .env.example
git commit -m "chore: align pythonpath and FLASK_APP for Flask-Migrate"
```

---

### Task 7: Update `idp-pegawai/docker-compose.yml` ke `flask db`

**Objective:** Hilangkan `alembic upgrade head` tercecer.

**Files:**
- Modify: `idp-pegawai/docker-compose.yml:6-13`

**Step 1 — Ganti command:**
```yaml
command: >
  sh -c "
  flask --app 'idp_pegawai:create_app()' db upgrade &&
  python scripts/seed_dev_org_unit.py &&
  flask --app 'idp_pegawai:create_app()' run --host=0.0.0.0 --port=9999
  "
```
Dan pastikan `FLASK_APP` konsisten; `TEST_DATABASE_URL: ""` tetap.

**Step 2 — Verifikasi:**
```bash
docker compose -f idp-pegawai/docker-compose.yml config --quiet && echo "compose OK"
```
Expected: `compose OK`.

**Step 3 — Commit:**
```bash
git add idp-pegawai/docker-compose.yml
git commit -m "chore: use flask db upgrade in idp-pegawai compose"
```

---

### Task 8: Konsolidasi `src/` vs `idp-pegawai/` (hentikan drift)

**Objective:** `src/idp_pegawai` saat ini banyak folder kosong + `__pycache__`; sumber kebenaran adalah `idp-pegawai/`. Pilih satu.

**Files:**
- Inspect: `src/idp_pegawai/__init__.py` (tidak ada), `src/idp_pegawai/consumer/*` (hanya pycache)
- Decide: **Opsi A** — kosongkan `src/` dari tracking dan jadikan `.gitignore` atau hapus folder kosong; **Opsi B** — jadikan `src/` shim yang import dari `idp-pegawai` (tidak disarankan).

**Step 1 — Rekomendasi Opsi A (paling rapi):**
```bash
git rm -r --cached src/idp_pegawai 2>&1 | head -n 20
rm -rf src/idp_pegawai
# atau jika masih ingin simpan template, pindahkan template ke idp-pegawai/templates
```
Jika `src/idp_pegawai/templates/ui` masih dipakai, sinkronkan:
```bash
diff -r idp-pegawai/templates src/idp_pegawai/templates 2>&1 | head -n 40
cp -a idp-pegawai/templates/ui/* src/idp_pegawai/templates/ui/ 2>&1 | head
```

**Step 2 — Update `.gitignore` jika perlu:**
```
src/
# atau
src/idp_pegawai/__pycache__/
```

**Step 3 — Verifikasi:**
```bash
pytest -q
git status --short
```
Expected: tidak ada import error; `src` tidak lagi jadi sumber drift.

**Step 4 — Commit:**
```bash
git add -A
git commit -m "chore: consolidate src vs idp-pegawai — single source in idp-pegawai"
```

---

### Task 9: Verifikasi Flask-Migrate end-to-end

**Objective:** Buktikan `flask db` bekerja dengan PostgreSQL nyata.

**Files:** tidak ubah kode, hanya verifikasi.

**Step 1 — Local (tanpa DB):**
```bash
flask --app 'idp_pegawai:create_app()' db current 2>&1 | head -n 20
flask --app 'idp_pegawai:create_app()' db history 2>&1 | head -n 30
pytest tests/unit/test_migration_definition.py tests/unit -q
```

**Step 2 — Dengan PostgreSQL nyata (di env yang punya global_postgresql):**
```bash
# di host WSL yang punya TEST_DATABASE_URL terisolasi
TEST_DATABASE_URL=postgresql+psycopg://postgres:xxx@global_postgresql:5432/db_sso_test \
  pytest tests/integration/test_migration_identity.py -q
# atau via docker python3-base
docker run --rm --network project_network -v $PWD:/usr/src/app -w /usr/src/app \
  -e TEST_DATABASE_URL=postgresql+psycopg://postgres:xxx@global_postgresql:5432/db_sso_test \
  python3-base:latest pytest tests/integration/test_migration_identity.py -v
```

**Step 3 — Manual flask db cycle (isolated DB):**
```bash
TEST_DATABASE_URL=postgresql+psycopg://... flask --app 'idp_pegawai:create_app()' db downgrade base
TEST_DATABASE_URL=postgresql+psycopg://... flask --app 'idp_pegawai:create_app()' db upgrade
TEST_DATABASE_URL=postgresql+psycopg://... flask --app 'idp_pegawai:create_app()' db current
```

Expected: history menampilkan `0001..0010`; downgrade/upgrade bersih; tidak ada table `pegawai` setelah downgrade base.

---

### Task 10 (Opsional): Pindah fisik `migrations/` ke `idp-pegawai/migrations/`

**Objective:** Jika user mau “tidak tercecer di root” secara fisik.

**Files:**
- Move: `migrations/` → `idp-pegawai/migrations/`
- Modify: `alembic.ini` (`script_location = idp-pegawai/migrations`)
- Modify: `idp-pegawai/extensions.py` (`Migrate(app, db, directory='idp-pegawai/migrations')`)
- Modify: `tests/unit/test_migration_definition.py` (path `MIGRATION`)
- Modify: `tests/integration/test_migration_identity.py` (`script_location`)

**Step 1:**
```bash
git mv migrations idp-pegawai/migrations
# update alembic.ini, extensions.py, tests
```

**Step 2 — Verifikasi:** `flask db current` tetap baca history lama.

**Step 3 — Commit:** `chore: move migrations into idp-pegawai/`

> Hanya lakukan jika diminta eksplisit — default tetap Opsi A (migrations di root tapi via `flask db`).

---

## 3. File yang Berubah (ringkas)

- `pyproject.toml` — tambah `Flask-Migrate`
- `idp-pegawai/extensions.py` — `db` single source + `migrate = Migrate()`
- `idp-pegawai/models/base.py` — re-export / hapus duplikasi `db`
- `idp-pegawai/__init__.py` — `migrate.init_app(app, db)`
- `migrations/env.py` — pakai `current_app` + `target_metadata`
- `alembic.ini` — `script_location` + hapus `prepend_sys_path` salah
- `idp-pegawai/docker-compose.yml` — `flask db upgrade`
- `src/` — konsolidasi/kosongkan
- (opsional) `tests/*` — update path jika migrations dipindah fisik

## 4. Test & Validation

- `pytest tests/unit/test_migration_definition.py -q` — downgrade drops every created index
- `pytest tests/integration/test_migration_identity.py -q` — schema + downgrade (butuh `TEST_DATABASE_URL`)
- `pytest -q` — full regression (expect 2 skipped bila tanpa DB)
- `flask db history/current/upgrade/downgrade` — di container `python3-base:latest` + `project_network`
- `docker compose -f idp-pegawai/docker-compose.yml config --quiet` — compose valid
- Manual SSO/token-exchange: `s1-jabar` → Keycloak → IDP `pegawai-profile.v1` tetap 200 (tidak boleh regresi)

## 5. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| `migrate.init_app` lupa → `flask db` error `No app` | Migration tidak jalan | Guard di factory + test `migrate in app.extensions` |
| Duplikasi `db` masih ada → `target_metadata` kosong | `flask db migrate` generate kosong | Satukan `db` single source + assert `db is db2` |
| `env.py` pakai `TEST_DATABASE_URL` di runtime | Destructive downgrade ke DB production | Hard guard: runtime hanya pakai `DATABASE_URL`/`Config.build_db_uri` |
| Memindahkan `migrations/` fisik tanpa `git mv` | History hilang, `alembic_version` mismatch | Pakai `git mv` + update `Migrate(directory=...)` + test path |
| `src/` drift vs `idp-pegawai/` | Import ambigu, pytest pythonpath salah | Konsolidasi ke `idp-pegawai/` single source, `src/` di-ignore/dihapus |
| SSO/token exchange regresi | `s1-jabar` tidak bisa fetch profile | Jangan ubah `INTERNAL_PROFILE_*` / `oidc/validator.py`; e2e test token exchange tetap hijau |

## 6. Open Questions

- Apakah `migrations/` harus **pindah fisik** ke `idp-pegawai/migrations/` atau cukup **di-drive via `flask db`** tapi tetap di root? (Plan default: tetap di root, Opsi A)
- Apakah `src/` masih dibutuhkan untuk sesuatu (mis. template fallback) atau boleh dihapus total?
- Versi `Flask-Migrate` pin eksak: `>=4.0,<5.0` atau `==4.0.7`?

---

## 7. Next Step

Jalankan Task 1–9 secara berurutan dengan `subagent-driven-development` (satu subagent per task, review spec + code quality). Setelah semua task hijau, jalankan `Task 9` end-to-end di environment dengan `global_postgresql` sebelum merge.
