# 37-idp-pegawai-local-auth-captcha-rbac — Plan Eksekusi TDD

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.  
> **Goal:** Menutup idp-pegawai yang masih open dengan login lokal + captcha image + RBAC tipis admin/operator + hardening, tanpa overkill.  
> **Architecture:** Dokumen `docs/architecture/37-idp-pegawai-local-auth-captcha-rbac-hardening-contract.md` (BEKU, tidak boleh dilanggar).  
> **Tech Stack:** Flask 3, SQLAlchemy 2, Alembic/Flask-Migrate, PostgreSQL `global_postgresql/db_sso`, Redis (captcha TTL + lockout counter), `python3-base:latest` + `captcha==0.7.0` + `Pillow==11.1.0`, `argon2-cffi`/`bcrypt`, `Flask-Limiter`/`Flask-WTF` (sudah ada).  
> **Boundary:** Forward migration `0003_create_idp_users.py` saja; jangan ubah `0001/0002`; evidence wajib Postgres nyata di `project_network`.

---

## 0. Current Context & Assumptions

- **Squash branch:** `master`/`staging`/`production` sudah `initial commit`; `development` jadi referensi. Slice ini dikerjakan di `development` dan commit kecil per slice.
- **Layout proper package:** `idp-pegawai/idp_pegawai/` sudah ada (factory `create_app`, `extensions.db/migrate`, `security/middleware.py` + `sanitization.py`, `access/catalog.py` 6 role). Reuse, jangan duplikasi.
- **Image:** `python3-base:latest` sudah ada `argon2-cffi`, `Flask-Limiter 4.1.1`, `redis`, `Flask-WTF`, `email-validator`; **belum ada** `captcha`/`Pillow` → wajib install slice 2.
- **DB:** `global_postgresql` `db_sso` via `TEST_DATABASE_URL`; `project_network` external.
- **Prinsip:** 1 kolom `role` (`admin`|`operator`) mapping ke `catalog.py`; tidak ada tabel `roles/permissions`.

---

## 1. Proposed Approach — 5 Slice TDD

```
Dok 37 (BEKU) ──► Slice 1 (model+validator) ──► Slice 2 (captcha) ──► Slice 3 (auth routes+lockout)
                                              ──► Slice 4 (rate limiter) ──► Slice 5 (CLI+admin users)
Tiap slice: RED → GREEN → REFACTOR → REGRESSION → EVIDENCE (Postgres) → COMMIT
```

---

## Slice 1 — Model IdpUser + Migrasi 0003 + Password Validator

### Objective
Tabel `idp_users` ada di Postgres + validator 12-char 4-kategori lolos test.

### Files
- Create: `idp-pegawai/idp_pegawai/models/idp_user.py`
- Create: `idp-pegawai/migrations/versions/0003_create_idp_users.py`
- Create: `idp-pegawai/idp_pegawai/security/password.py`
- Modify: `idp-pegawai/idp_pegawai/models/__init__.py` (export IdpUser)
- Create: `idp-pegawai/tests/unit/security/test_password_validator.py`
- Create: `idp-pegawai/tests/integration/models/test_idp_user_constraints.py`
- Modify: `idp-pegawai/idp_pegawai/config.py` (optional: `LOGIN_MAX_FAILS`, `LOGIN_LOCKOUT_MINUTES` defaults — bisa di Slice 4 juga)

### TDD Steps
1. **RED:** Tulis `test_password_validator.py` — Tabel truth: `Str0ng!Pass#12` lolos; `password123`/`<12`/`tanpa upper`/`tanpa symbol`/`mengandung username`/`AAA` triple → error list bahasa Indonesia.
2. Run `docker run --rm -v $PWD/idp-pegawai:/usr/src/app -w /usr/src/app --network project_network python3-base:latest pytest tests/unit/security/test_password_validator.py -q` → FAIL (module belum ada).
3. **GREEN:** Implement `security/password.py` `validate_password_strength(password, username="", email="") -> list[str]` sesuai §5 Dok 37 (12, upper/lower/digit/symbol, username/email substring >=3, triple repeat, sequence abc/123).
4. Re-run → GREEN.
5. **RED (DB):** Tulis `test_idp_user_constraints.py` — create IdpUser normal OK; duplicate username (case-insensitive lower) → IntegrityError; role invalid → CheckViolation; soft delete still queryable; uuid unique.
6. **GREEN (DB):** Implement `models/idp_user.py` (columns §4.2, `lower(username)` handling, `password_hash` setter via werkzeug/argon2, `check_password` method, `is_locked` property).
7. Create migration `0003_create_idp_users.py` (see DDL §4.2) — `upgrade`/`downgrade` reversible.
8. **EVIDENCE:** `TEST_DATABASE_URL=... pytest tests/integration/models/test_idp_user_constraints.py -v` + `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` di `global_postgresql`.
9. **REGRESSION:** `pytest -q` full suite.

### Verification
```bash
docker run --rm -v $PWD/idp-pegawai:/usr/src/app -w /usr/src/app --network project_network \
  -e TEST_DATABASE_URL=postgresql+psycopg://postgres:***@global_postgresql:5432/db_sso \
  python3-base:latest pytest tests/unit/security/test_password_validator.py tests/integration/models/test_idp_user_constraints.py -v

docker compose exec kumjabar_idp flask --app 'idp_pegawai:create_app()' db upgrade
docker compose exec kumjabar_idp flask --app 'idp_pegawai:create_app()' db downgrade -1 && flask --app 'idp_pegawai:create_app()' db upgrade
```

### Pitfalls
- Username unique harus case-insensitive — handle di app `lower()` + index `lower(username)`, bukan hanya Python check.
- `metadata` column conflict — pakai `metadata_` mapping seperti `ModelBase`.
- Jangan hardcode secret di migration/test.

---

## Slice 2 — Captcha Lokal (Image + Redis TTL)

### Objective
`GET /login` selalu render captcha image; `captcha_id` sekali pakai TTL 5m; verify anti-replay.

### Files
- Install: `captcha==0.7.0`, `Pillow==11.1.0` (via `requirements.txt` atau `pip install` di Dockerfile/compose — sesuai §12 Dok 37)
- Create: `idp-pegawai/idp_pegawai/security/captcha.py` (`generate_captcha() -> {captcha_id, image_base64, answer_for_test?}`, `verify_captcha(captcha_id, answer) -> bool`, `store: redis` with fallback session)
- Create: `idp-pegawai/tests/unit/security/test_captcha_service.py`
- Create: `idp-pegawai/tests/integration/security/test_captcha_ttl.py` (optional, mock redis)
- Modify: `idp-pegawai/idp_pegawai/config.py` (CAPTCHA_TTL=300, CAPTCHA_LENGTH=5 — kalau belum ada)

### TDD Steps
1. **RED:** Test `generate_captcha` returns `captcha_id` uuid + `image_base64` startswith `data:image/png;base64,` + stored value retrievable; `verify_captcha` wrong → False + delete; correct → True + delete (sekali pakai); expired (mock TTL) → False.
2. Install libs in container: `docker run --rm python3-base:latest pip install captcha==0.7.0 Pillow==11.1.0 && python -c "from captcha.image import ImageCaptcha; print('ok')"` → must OK.
3. **GREEN:** Implement `security/captcha.py` — `ImageCaptcha(width=160,height=60)` random 5 chars `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` (tanpa 0/O/I/1), base64 PNG, `redis.setex(f"captcha:{id}", 300, text.lower())`, `verify` does `get+delete` atomic-ish.
4. Fallback: if redis unavailable, use `session` dict (for test/dev) + log warning.
5. **EVIDENCE:** Unit tests dengan `fakeredis` atau mock; no PII in logs.

### Verification
```bash
docker run --rm --network project_network -v $PWD/idp-pegawai:/usr/src/app -w /usr/src/app \
  python3-base:latest sh -c "pip install -q captcha==0.7.0 Pillow==11.1.0 && pytest tests/unit/security/test_captcha_service.py -v"
```

---

## Slice 3 — Auth Service + Routes /login /logout + Lockout + Sanitasi

### Objective
Login flow lengkap: captcha dulu → lockout 5/15m → hash verify → session → audit generik.

### Files
- Create: `idp-pegawai/idp_pegawai/services/auth_service.py` (`authenticate(username, password, captcha_id, captcha_answer, ip) -> (user|None, error_code, captcha_new?)`)
- Create: `idp-pegawai/idp_pegawai/api/auth.py` (Blueprint `auth_bp`: `GET /login`, `POST /login`, `POST /logout`)
- Create: `idp-pegawai/idp_pegawai/templates/auth/login.html` (form username/password/captcha + hidden captcha_id + CSRF)
- Create: `idp-pegawai/idp_pegawai/repositories/idp_user_repository.py` (query-only: `get_by_username`, `get_by_id`)
- Modify: `idp-pegawai/idp_pegawai/__init__.py` (register `auth_bp`, `CSRFProtect`, session config if needed)
- Create: `idp-pegawai/tests/contract/api/test_auth_login.py`
- Create: `idp-pegawai/tests/integration/services/test_auth_lockout.py`

### TDD Steps
1. **RED contract:** `GET /login` → 200 + contains `captcha` + `captcha_id`; `POST /login` tanpa captcha → 400 + captcha baru; captcha salah → 400 generik + audit `captcha_failed`; password salah → 400 generik `Username, password, atau captcha salah` + `failed_attempts++`; 5x salah → `locked_until` set + 403 `akun terkunci`; sukses → 302/200 + `session['user_id']` + `failed_attempts=0`; XSS payload `"<script>"` di username → escaped.
2. **GREEN:** Implement `repositories/idp_user_repository.py` (lower username lookup, `is_active` check), `services/auth_service.py` (order: verify captcha → lookup user active → check locked_until → verify_password `check_password_hash` → update counters + `last_login_at` → audit dict), `api/auth.py` (GET generate captcha, POST call service, set `session['user_id']`, `session['role']`, `session.permanent=True`, generic error rendering, new captcha on fail).
3. Sanitasi: `username = sanitize_text(form.username.data, max_length=80)` before lookup; template autoescape stays on.
4. Audit: log `login_failed`/`login_locked`/`login_success`/`captcha_failed` tanpa password/captcha plain (only `username`, `ip`, `code`).
5. **EVIDENCE:** Integration test with real Postgres + redis/mock; `login_locked` timing test.

### Verification
```bash
TEST_DATABASE_URL=... pytest tests/contract/api/test_auth_login.py tests/integration/services/test_auth_lockout.py -v
# Manual smoke
curl -c /tmp/c.jar http://127.0.0.1:9999/login | grep captcha
```

---

## Slice 4 — Rate Limiter 2 Lapis + Decorators

### Objective
Per-IP 10/menit 429 + per-username lockout integration + `login_required`/`role_required('admin')`.

### Files
- Modify: `idp-pegawai/idp_pegawai/security/middleware.py` (extend `SlidingWindowLimiter` for `/login` stricter 10/min, or use `Flask-Limiter` `@limiter.limit("10/minute")`)
- Create: `idp-pegawai/idp_pegawai/access/decorators.py` (or extend `access/guards.py`: `login_required`, `role_required(*roles)`)
- Modify: `idp-pegawai/idp_pegawai/config.py` (`RATE_LIMIT_LOGIN_PER_MINUTE=10`, `LOGIN_MAX_FAILS=5`, `LOGIN_LOCKOUT_MINUTES=15`)
- Create: `idp-pegawai/tests/contract/api/test_rate_limiter.py`
- Create: `idp-pegawai/tests/unit/access/test_decorators.py`

### TDD Steps
1. **RED:** 11 POST /login dalam 60s dari same IP → 429 + `Retry-After`; `GET /admin/users` tanpa session → 401/302 to /login; sebagai operator → 403; sebagai admin → 200.
2. **GREEN:** Wire `Flask-Limiter` or extend `middleware.SlidingWindowLimiter` with key=`X-Forwarded-For`/`remote_addr` per-route; per-username already in `auth_service` (Slice 3) — add redis counter `login_fail:{username}` as second check; implement decorators checking `session.get('user_id')` + `session.get('role')`.
3. Config: allow `RATE_LIMIT_DISABLED` in Testing.
4. **EVIDENCE:** Contract tests hit limiter deterministically (mock time/monotonic if needed).

---

## Slice 5 — CLI create-admin + /admin/users (admin only) + Hardening Headers

### Objective
Seed admin pertama idempotent + CRUD users minimal + headers final.

### Files
- Create: `idp-pegawai/idp_pegawai/operations/create_admin.py` (core logic)
- Modify: `idp-pegawai/idp_pegawai/__init__.py` (register `@app.cli.command("create-admin")` with click options `--username --password --role --email`)
- Create: `idp-pegawai/idp_pegawai/api/admin_users.py` (Blueprint `admin_users_bp`: `GET /admin/users`, `POST /admin/users`, `POST /admin/users/<id>/deactivate`)
- Create: `idp-pegawai/idp_pegawai/templates/admin/users.html`
- Modify: `idp-pegawai/idp_pegawai/security/middleware.py` (ensure CSP/HSTS headers on auth pages)
- Create: `idp-pegawai/tests/integration/operations/test_create_admin_cli.py`
- Create: `idp-pegawai/tests/contract/api/test_admin_users.py`

### TDD Steps
1. **RED CLI:** `flask create-admin --username admin --password Str0ng!Pass#12 --role admin` → `[OK] created`; run again → `[SKIP] already exists`; weak password → error + hint 4 kategori; invalid role → error.
2. **GREEN CLI:** Implement `operations/create_admin.py` calling `validate_password_strength` + `IdpUser` create with hashed password; idempotent check `lower(username)` exists → skip.
3. **RED admin_users:** `POST /admin/users` as operator → 403; as admin with valid payload → 201 + list contains user; deactivate → soft delete + cannot login; duplicate username → 409.
4. **GREEN:** Implement `api/admin_users.py` with `@login_required @role_required('admin')`, validasi password, `sanitize_text`, audit `user_created`/`user_deactivated`.
5. **Hardening:** Ensure `security_headers` after_request covers `/login`/`/admin/*`; test `X-Content-Type-Options: nosniff` present.
6. **EVIDENCE:** Postgres integration for CLI idempotent + downgrade/upgrade; `pytest -q` full green; `docker compose config --quiet` + `project_network` inspect.

### Verification
```bash
# CLI
docker compose exec kumjabar_idp flask --app 'idp_pegawai:create_app()' create-admin --username admin --password 'Str0ng!Pass#12' --role admin
docker compose exec kumjabar_idp flask --app 'idp_pegawai:create_app()' create-admin --username admin --password 'Str0ng!Pass#12' --role admin  # must SKIP

# Admin users
TEST_DATABASE_URL=... pytest tests/contract/api/test_admin_users.py tests/integration/operations/test_create_admin_cli.py -v
pytest -q
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

---

## 2. Evidence Gates (per Slice, Postgres nyata)

```bash
# Cepat
pytest tests/unit tests/contract -q
# Integrasi + Postgres
TEST_DATABASE_URL=postgresql+psycopg://postgres:***@global_postgresql:5432/db_sso pytest tests/integration -q
# Full
TEST_DATABASE_URL=... pytest -q
# Migrasi
alembic upgrade head; alembic downgrade base; alembic upgrade head
# Docker
docker compose config --quiet
docker network inspect project_network | grep global_postgresql
```

**Gate:** Jangan lanjut slice N+1 jika slice N full suite gagal atau review blocked (AGENTS.md).

---

## 3. Files Likely to Change (summary)

| File | Slice |
|---|---|
| `idp_pegawai/models/idp_user.py`, `security/password.py`, `migrations/0003_*` | 1 |
| `security/captcha.py` + `captcha`/`Pillow` install | 2 |
| `services/auth_service.py`, `api/auth.py`, `repositories/idp_user_repository.py`, `templates/auth/login.html` | 3 |
| `security/middleware.py`, `access/decorators.py`, `config.py` | 4 |
| `operations/create_admin.py`, `api/admin_users.py`, `templates/admin/users.html` | 5 |
| `models/__init__.py`, `__init__.py` (factory) | 1,3,5 |

---

## 4. Commit Plan

```
feat(auth): Slice1 model idp_users + password validator 12/4-kategori + migrasi 0003
feat(auth): Slice2 captcha lokal image + Redis TTL 5m sekali pakai
feat(auth): Slice3 login/logout + lockout 5/15m + sanitasi XSS audit generik
feat(auth): Slice4 rate limiter per-IP + per-username + decorators RBAC tipis
feat(auth): Slice5 CLI create-admin idempotent + /admin/users admin-only + hardening
```

Jangan gabung migration + UI + worker dalam satu commit.

---

Status: **APPROVED FOR DEVELOPMENT** — eksekusi via `delegate_task` per slice, `development` branch, evidence `global_postgresql`.
