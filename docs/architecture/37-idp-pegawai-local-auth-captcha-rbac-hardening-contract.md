# 37 - Kontrak Local Auth, Captcha, RBAC Tipis & Hardening IDP Pegawai

Status: **BEKU / APPROVED FOR DEVELOPMENT** — siap eksekusi TDD  
Proyek: `kumjabar-sso`  
Tanggal: 2026-09-30  
Melanjutkan: Dokumen 01–36  
Granularity: Slice lokal IDP Pegawai (menutup UI/API yang masih open)  
Branch acuan: `development` (referensi), `master`/`staging`/`production` = `initial commit` (squash)  
Author: brainstorming Telegram + review `catalog.py`/`config.py`/`security/`/`docker-compose.yml`

> Dokumen ini adalah **panduan baku** sebelum koding. Semua slice TDD wajib mengacu ke sini. Tidak boleh menambah role baru, field `metadata` jabatan, atau policy DSL di luar yang dibekukan di sini.

---

## 1. Tujuan — Bahasa Bayi

**Masalah hari ini:** IDP Pegawai seperti **kantor yang pintunya terbuka** — siapa pun bisa masuk dan ubah data pegawai.

**Solusi:** Pasang **satpam di pintu** (login) yang:
1. Minta **KTP** (username + password kuat)
2. Minta **teka-teki gambar** (captcha) — biar robot tidak bisa masuk
3. Cek **kartu akses** (role `admin` vs `operator`) — hanya admin boleh buka ruang arsip (kelola users)

**Hasil akhir:** Operator tetap bisa input pegawai, tapi tidak bisa bikin user baru atau hapus user. Admin bisa semuanya. Semua percobaan login dicatat (audit) tanpa simpan password.

---

## 2. Analogi Lengkap (Biar Tidak Overkill)

```
Tanpa RBAC (Opsi A)         RBAC Tipis 2 Role (Opsi B - DIPILIH)
===================         ===============================
1 kunci untuk semua   vs    2 kunci: kunci gudang & kunci arsip
Murah di awal         vs    Murah juga, cuma beda 1 kolom di DB
Bahaya: OB bisa        vs    Aman: OB hanya bisa bersihkan gudang
  buka brankas                tidak bisa buka brankas

Overkill RBAC Enterprise (TIDAK DIPILIH)
========================================
Seperti bikin 20 kunci + 50 aturan + tabel izin ribet
Padahal kantor cuma punya 2 ruangan -> buang waktu
```

> **Keputusan final:** Opsi B tipis. Cost = 1 kolom `role` + 1 decorator `role_required('admin')`. Bukan 5 tabel RBAC enterprise. Tidur nyenyak tanpa over-engineering.

---

## 3. Keputusan yang Dibekukan

| # | Item | Keputusan BEKU | Alasan |
|---|------|----------------|--------|
| 1 | **RBAC** | **Opsi B tipis: `admin` vs `operator`** | Mapping ke `catalog.py` existing, 1 kolom, anti bongkar ulang |
| 2 | **Captcha** | **Lokal image, selalu tampil** | Tanpa Google reCAPTCHA, tanpa internet, privacy instansi aman |
| 3 | **Password** | **Min 12 karakter, 4 kategori wajib** | Standar BSSN/OWASP, bukan 8 |
| 4 | **Rate limiter** | **2 lapis: per-IP + per-username lockout** | Cegah brute force |
| 5 | **Sanitasi** | **Reuse `sanitize_text()` + Jinja autoescape** | Cegah XSS tanpa lib baru |
| 6 | **CLI seed** | **`flask create-admin` idempotent** | Solusi "lucu gak bisa masuk" saat deploy pertama |
| 7 | **Migrasi** | **Forward `0003_create_idp_users.py`** | Jangan edit `0001/0002`, `development` tetap audit referensi |
| 8 | **Session** | **HttpOnly + Secure (prod) + SameSite=Lax, 12 jam** | Hardening gratis |

Yang **TIDAK** dibekukan sekarang (phase 2): 2FA, password history, email reset, OAuth.

---

## 4. Desain Tabel `idp_users`

### 4.1 Bahasa Bayi
Tabel ini seperti **buku daftar satpam** — tiap baris = 1 orang yang boleh masuk kantor. Ada ID, nama (username), kunci rahasia (hash password), kartu akses (role), dan catatan "sedang dihukum" (lockout).

### 4.2 Schema Detail

```sql
-- PostgreSQL, authority: IDP Pegawai DB (global_postgresql / db_sso)
-- File migrasi: idp-pegawai/migrations/versions/0003_create_idp_users.py

CREATE TABLE idp_users (
    id               BIGSERIAL PRIMARY KEY,
    uuid             UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(), -- pgcrypto
    username         VARCHAR(80) NOT NULL,        -- disimpan lowercase, unique
    email            VARCHAR(255),                -- nullable, unique jika diisi
    password_hash    VARCHAR(255) NOT NULL,       -- argon2/bcrypt, never plain
    role             VARCHAR(20) NOT NULL DEFAULT 'operator'
                     CHECK (role IN ('admin','operator')),
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    failed_attempts  INTEGER NOT NULL DEFAULT 0,
    locked_until     TIMESTAMPTZ,                 -- NULL = tidak terkunci
    last_login_at    TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at       TIMESTAMPTZ,                 -- soft delete ala ModelBase
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (uuid),
    UNIQUE (username)                             -- index lowercase handled app
);
CREATE INDEX ix_idp_users_username ON idp_users (lower(username));
CREATE INDEX ix_idp_users_email ON idp_users (lower(email)) WHERE email IS NOT NULL;
CREATE INDEX ix_idp_users_is_active ON idp_users (is_active);
CREATE INDEX ix_idp_users_deleted_at ON idp_users (deleted_at);
```

### 4.3 Aturan Model (Python `idp_pegawai/models/idp_user.py`)

- `username` selalu `strip().lower()`, 3–80 char, regex `^[a-z0-9._-]+$`
- `email` opsional, jika diisi validasi `email-validator`, simpan lowercase
- `password_hash` via `werkzeug.security.generate_password_hash` atau `argon2-cffi` (sudah ada di image)
- `role` default `operator`, hanya `admin` boleh akses `/admin/users`
- `is_active=False` atau `deleted_at IS NOT NULL` = tidak bisa login (403)
- `uuid` default `uuid4()` di Python, tapi DB juga `gen_random_uuid()` sebagai fallback

### 4.4 Mapping ke RBAC Existing (`access/catalog.py`)

```
idp_users.role = 'admin'    ->  Role.ACCESS_ADMIN + Role.SECURITY_ADMIN (view audit)
idp_users.role = 'operator' ->  Role.IMPORT_OPERATOR (input pegawai + import)

-- Tidak membuat Role baru. Reuse Capability existing:
admin:    idp.pegawai.create/update/deactivate, idp.access_grant.*, idp.audit.view
operator: idp.pegawai.view/create/update, idp.import.*
```

---

## 5. Password Validator — 4 Kategori + 12 Karakter

### 5.1 Bahasa Bayi
Password seperti **kombinasi brankas**: harus ada huruf BESAR, huruf kecil, angka, dan simbol. Minimal 12 putaran (karakter). Tidak boleh pakai nama sendiri sebagai kombinasi.

### 5.2 Aturan Lengkap (`idp_pegawai/security/password.py`)

```python
def validate_password_strength(password: str, username: str = "", email: str = "") -> list[str]:
    """
    Return [] jika kuat, atau list pesan error bahasa Indonesia.
    Aturan BEKU:
    1. min 12 karakter, max 128
    2. wajib ada: uppercase [A-Z] + lowercase [a-z] + digit [0-9] + symbol [!@#$%^&*...]
    3. tidak boleh mengandung username/email (case-insensitive, potongan >=3 char)
    4. tidak boleh 3 char berurutan sama (aaa, 111) atau sequence (abc, 123, qwerty potongan)
    5. tidak boleh 4 char keyboard berurutan (optional, warning)
    """
```

**Contoh:**

| Password | Hasil |
|---|---|
| `Str0ng!Pass#12` | ✅ Lolos |
| `password123` | ❌ Kurang: no upper, no symbol, <12 |
| `Admin123!` | ❌ <12 + mengandung "admin" |
| `AAAbbb123!!!` | ❌ Ada `AAA` 3 berurutan |
| `Qwerty123!@#` | ❌ Mengandung sequence `qwerty` |

Pesan error **selalu bahasa Indonesia** dan spesifik (bukan "password lemah" doang).

---

## 6. Captcha Lokal — Selalu Tampil

### 6.1 Bahasa Bayi
Captcha seperti **teka-teki gambar** di pintu. Tiap mau masuk, satpam kasih gambar angka/huruf acak. Kamu harus baca dan ketik. Gambar hanya berlaku 5 menit, lalu hangus.

### 6.2 Spesifikasi

- **Library:** `captcha` (ImageCaptcha) + `Pillow` (render gambar)
- **Storage:** Redis (`REDIS_URL` existing) dengan key `captcha:{uuid}` TTL 300 detik. Fallback: `Flask session` jika Redis down (fail-closed, log warning).
- **Flow:**
  1. `GET /login` -> `captcha_id = uuid4()` + `text = random 5 char [A-Z0-9 tanpa 0/O/I]` + `image_base64 = ImageCaptcha().generate(text)` -> simpan `redis.setex(captcha_id, 300, text.lower())` -> render `<img src="data:image/png;base64,...">` + `<input name="captcha_answer">` + `<input type="hidden" name="captcha_id">`
  2. `POST /login` -> ambil `captcha_id` + `captcha_answer` -> `expected = redis.get(captcha_id)` -> jika `None` => "captcha kadaluarsa, coba lagi" -> `if answer.lower() != expected.lower()` => 400 + generate captcha baru -> `redis.delete(captcha_id)` (sekali pakai, anti replay) -> baru lanjut cek username/password
- **Keamanan:** Jawaban tidak pernah di-log, tidak di-audit plain, hanya `captcha_failed` event. Gambar diberi noise + line agar OCR sulit. `captcha_id` UUID v4, tidak sequential.

### 6.3 Diagram Captcha

```mermaid
sequenceDiagram
    participant Browser
    participant Flask
    participant Redis
    Browser->>Flask: GET /login
    Flask->>Flask: text=random(5), id=uuid4()
    Flask->>Redis: SETEX captcha:{id} 300 text
    Flask-->>Browser: HTML + <img base64> + hidden captcha_id
    Browser->>Flask: POST /login (username, password, captcha_id, answer)
    Flask->>Redis: GET captcha:{id}
    alt captcha missing/expired
        Flask-->>Browser: 400 captcha kadaluarsa + captcha baru
    else answer salah
        Flask->>Redis: DEL captcha:{id}
        Flask-->>Browser: 400 captcha salah + captcha baru
    else answer benar
        Flask->>Redis: DEL captcha:{id}
        Flask->>Flask: lanjut cek password/lockout
    end
```

---

## 7. Flow Login / Logout Lengkap

### 7.1 Diagram Utama

```mermaid
flowchart TD
    A[GET /login] --> B[Generate captcha_id + image<br/>Simpan Redis TTL 5m]
    B --> C[Render form: username, password, captcha]
    C --> D[POST /login]
    D --> E{Captcha valid?}
    E -- Tidak --> C
    E -- Ya --> F{User ada & active?}
    F -- Tidak --> G[Hitung gagal + audit<br/>Pesan generik]
    G --> C
    F -- Ya --> H{Terkunci? locked_until > now}
    H -- Ya --> I[403 akun terkunci + audit]
    I --> C
    H -- Tidak --> J{Password hash cocok?}
    J -- Tidak --> K[failed_attempts++<br/>Jika >=5 lock 15m<br/>Audit gagal]
    K --> C
    J -- Ya --> L[Reset failed_attempts=0<br/>last_login_at=now<br/>session user_id, role<br/>Audit sukses]
    L --> M[Redirect /ui/ sesuai role]
    M --> N[POST /logout -> session.clear]

    style E fill:#fff3cd
    style H fill:#f8d7da
    style L fill:#d4edda
```

### 7.2 Anti-Enumeration
Pesan gagal **selalu generik**: `"Username, password, atau captcha salah"` — jangan bocorkan "username tidak ditemukan" vs "password salah". Ini mencegah attacker tebak username.

### 7.3 Routes & Decorator

```
GET  /login              -> form + captcha (public)
POST /login              -> proses + rate limiter + audit
POST /logout             -> clear session (login_required)
GET  /admin/users        -> list users (role_required admin)
POST /admin/users        -> create user (admin, validasi password)
POST /admin/users/<id>/deactivate -> soft delete (admin)

Decorators:
@login_required           -> cek session['user_id'] ada & user active
@role_required('admin')  -> cek session['role']=='admin' else 403
@rate_limited             -> cek per-IP + per-username (lihat §9)
```

---

## 8. RBAC Tipis — Matrix Akses

| Fitur | operator | admin |
|---|:---:|:---:|
| Login + captcha | ✅ | ✅ |
| Lihat dashboard `/ui` | ✅ | ✅ |
| Lihat/input/edit pegawai | ✅ | ✅ |
| Upload/validasi import (dry-run) | ✅ | ✅ |
| Download template import | ✅ | ✅ |
| **Approve import** | ❌ | ✅ |
| **Apply import** | ❌ | ✅ |
| **Kelola org unit (create/update/deactivate)** | ❌ | ✅ |
| **Kelola users (`/admin/users`)** | ❌ | ✅ |
| **Lihat audit login** | ❌ | ✅ |

> Implementasi: 1 `if` di route, bukan tabel permissions. Contoh:
> ```python
> @ui_bp.get("/admin/users")
> @login_required
> @role_required("admin")
> def list_users(): ...
> ```

---

## 9. Rate Limiter & Lockout — 2 Lapis

### 9.1 Bahasa Bayi
- **Lapis 1 (per-IP):** Jika 1 komputer coba 10x/menit, pintu dikunci untuk IP itu (429).
- **Lapis 2 (per-username):** Jika 1 username salah 5x/15 menit, akun dikunci 15 menit (`locked_until`).

### 9.2 Spesifikasi

- **Per-IP:** `SlidingWindowLimiter(limit=10, window=60)` via `Flask-Limiter` atau `security/middleware.py` existing. Key = `X-Forwarded-For` atau `remote_addr`. Return `429 {code: rate_limited}` + `Retry-After` header. Diuji: 11 request dalam 60 detik => 429.
- **Per-username:** `failed_attempts` counter di `idp_users`. Tiap gagal `++`. Jika `>=5` => `locked_until = now + 15 menit`. Tiap sukses `reset 0`. Login saat `locked_until > now` => `403 akun terkunci, coba lagi setelah ...` + audit. Counter juga di-Redis `login_fail:{username}` TTL 15m untuk double-check tanpa query DB tiap hit.
- **Konfigurasi:** `RATE_LIMIT_LOGIN_PER_MINUTE=10`, `LOGIN_MAX_FAILS=5`, `LOGIN_LOCKOUT_MINUTES=15` via `.env` (default di `config.py`).

### 9.3 Diagram Lockout

```mermaid
stateDiagram-v2
    [*] --> Active: failed=0
    Active --> Active: gagal 1-4 (failed++)
    Active --> Locked: gagal ke-5 (locked_until=+15m)
    Locked --> Locked: coba login => 403
    Locked --> Active: lewat 15m & login sukses (reset)
    Active --> Active: login sukses (reset 0)
```

---

## 10. Session & Sanitasi Hardening

- **Session:** `SESSION_KEY_PREFIX=idpjabar_`, `PERMANENT_SESSION_LIFETIME=12 jam`, `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SECURE=True` (prod, `False` di dev), `SESSION_COOKIE_SAMESITE=Lax`, `SECRET_KEY` dari `.env` (min 32 char). Logout wajib `session.clear()`.
- **Sanitasi XSS:** Input `username`/`email` lewat `sanitize_text(max_length=80)` existing (`security/sanitization.py`): hapus control chars, `html.escape`. Template Jinja tetap `autoescape`. Tidak echo password/captcha answer ke HTML/log.
- **CSRF:** `Flask-WTF` `CSRFProtect` aktif untuk `POST /login`/`/logout`/`/admin/*` (token di form). Test: POST tanpa token => 400.
- **Headers:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `CSP: default-src 'self'` via `security/middleware.py`.
- **Audit:** Tiap `login_success`, `login_failed`, `login_locked`, `captcha_failed`, `user_created`, `user_deactivated` dicatat tanpa password/captcha plain. IP + user-agent + timestamp dicatat.

---

## 11. CLI Seed Admin — Solusi "Lucu Gak Bisa Masuk"

### 11.1 Bahasa Bayi
Seperti **kunci cadangan** saat kantor baru jadi. Tukang (devops) bisa bikin admin pertama lewat terminal, tanpa harus buka pintu dulu.

### 11.2 Spesifikasi

```bash
# Dari host (development)
cd idp-pegawai
python -m flask --app 'idp_pegawai:create_app()' create-admin \
  --username admin \
  --password 'Str0ng!Pass#12' \
  --role admin \
  --email admin@jabarprov.go.id

# Via Docker
docker compose exec kumjabar_idp flask --app 'idp_pegawai:create_app()' create-admin \
  --username admin --password 'Str0ng!Pass#12' --role admin

# Output idempotent:
# [OK] admin created (id=1, role=admin)
# [SKIP] username 'admin' already exists (id=1) — tidak duplikat
```

- **Validasi:** Password CLI pakai `validate_password_strength()` yang sama (12 char + 4 kategori). Jika lemah => error + hint.
- **Idempotent:** Jika username sudah ada, tidak error, hanya skip + log warning (aman di-run ulang saat deploy).
- **Implementasi:** `idp_pegawai/operations/create_admin.py` + `Flask CLI` `@app.cli.command("create-admin")` via `click`.

---

## 12. Requirements Library untuk `python3-base:latest`

### 12.1 Hasil Inspeksi Image Saat Ini (2026-09-30)

```bash
docker run --rm python3-base:latest pip list | grep -E "Flask|argon|bcrypt|redis|Pillow|captcha|Limiter"
# Ada: Flask 3.1.3, Flask-Limiter 4.1.1, argon2-cffi 25.1.0, bcrypt 5.0.0,
#      redis 7.4.1, Flask-WTF 1.3.0, cryptography 50.0.1
# TIDAK ADA: Pillow, captcha
```

| Library | Versi Rekomendasi | Status di image | Wajib Install? | Alasan |
|---|---|---|---|---|
| `captcha` | `0.7.0` | ❌ Belum ada | **YA** | Generate image captcha lokal |
| `Pillow` | `11.1.0` | ❌ Belum ada | **YA** | Dependency `captcha` untuk render PNG |
| `Flask-Limiter` | `4.1.1` | ✅ Sudah ada | Tidak | Rate limiter per-IP (reuse) |
| `argon2-cffi` | `25.1.0` | ✅ Sudah ada | Tidak | Hash password (prefer argon2) |
| `bcrypt` | `5.0.0` | ✅ Sudah ada | Tidak | Alternatif hash |
| `redis` | `7.4.1` | ✅ Sudah ada | Tidak | Store captcha + lockout counter |
| `Flask-WTF` | `1.3.0` | ✅ Sudah ada | Tidak | CSRF |
| `email-validator` | `2.3.0` | ✅ Sudah ada | Tidak | Validasi email |

### 12.2 Cara Install (Pilih Salah Satu)

**Opsi A — Tambah ke `idp-pegawai/requirements.txt` (jika ada) atau buat:**

```txt
# idp-pegawai/requirements.txt
captcha==0.7.0
Pillow==11.1.0
```

**Opsi B — Patch Dockerfile / docker-compose command (tanpa ubah image base):**

```yaml
# idp-pegawai/docker-compose.yml -> command
command: >
  sh -c "pip install --no-cache-dir captcha==0.7.0 Pillow==11.1.0 &&
  flask --app 'idp_pegawai:create_app()' db upgrade &&
  python scripts/seed_dev_org_unit.py &&
  flask --app 'idp_pegawai:create_app()' run --host=0.0.0.0 --port=9999"
```

**Opsi C — Build image turunan (rekomendasi production):**

```dockerfile
# idp-pegawai/deploy/Dockerfile
FROM python3-base:latest
RUN pip install --no-cache-dir captcha==0.7.0 Pillow==11.1.0
COPY . /usr/src/app
WORKDIR /usr/src/app
```

> **Catatan:** `captcha 0.7.0` butuh `Pillow` — install keduanya bersamaan. Test lokal: `docker run --rm python3-base:latest pip install captcha Pillow && python -c "from captcha.image import ImageCaptcha; print('ok')"`

---

## 13. Diagram Arsitektur Keseluruhan

```mermaid
flowchart LR
    subgraph Browser
        U[User]
        C[Captcha Image]
    end
    subgraph Flask["Flask idp_pegawai"]
        L[POST /login]
        A[Auth Service]
        R[IdpUser Model]
        S[Session + RBAC]
        M[Security Middleware]
    end
    subgraph Infra["Infra"]
        PG[(PostgreSQL<br/>global_postgresql/db_sso)]
        RD[(Redis)]
    end

    U -->|username+password+captcha| L
    L --> M --> A
    A -->|verify captcha| RD
    A -->|check lockout| R
    R --> PG
    A -->|verify hash| R
    A -->|set session| S
    S -->|role admin/operator| U

    style L fill:#d4edda
    style M fill:#fff3cd
    style PG fill:#cce5ff
```

---

## 14. Yang TIDAK Dilakukan (Biar Tidak Overkill)

- ❌ Tidak bikin tabel `roles`, `permissions`, `role_user` (cukup 1 kolom `role`)
- ❌ Tidak bikin policy DSL generic (`if can("pegawai.*")`) — hanya decorator eksplisit
- ❌ Tidak simpan captcha answer di DB (hanya Redis TTL)
- ❌ Tidak pakai Google reCAPTCHA / hCaptcha (butuh API key + internet)
- ❌ Tidak pakai JWT untuk session browser (cukup Flask session cookie)
- ❌ Tidak ubah `catalog.py` / `grants.py` existing — hanya mapping
- ❌ Tidak downgrade/reset DB — hanya forward migration 0003

---

## 15. Acceptance Criteria & Evidence Gate

### 15.1 Fungsional

- [ ] `POST /login` tanpa captcha => 400 + captcha baru
- [ ] `POST /login` captcha salah => 400 generik + captcha baru + audit `captcha_failed`
- [ ] `POST /login` password salah 5x => `locked_until` + 15m + 403
- [ ] `POST /login` sukses => session terisi, `failed_attempts=0`, redirect sesuai role
- [ ] `GET /admin/users` sebagai operator => 403
- [ ] `GET /admin/users` sebagai admin => 200 + list
- [ ] CLI `create-admin` idempotent + validasi 12 char + 4 kategori
- [ ] Rate limiter per-IP: 11 hit/menit => 429
- [ ] XSS payload di username => di-escape, tidak tereksekusi

### 15.2 Evidence Wajib (PostgreSQL nyata, bukan SQLite)

```bash
TEST_DATABASE_URL=postgresql+psycopg://postgres:***@global_postgresql:5432/db_sso \
  pytest tests/integration -k idp_user -q

# Migration
alembic upgrade head && alembic downgrade -1 && alembic upgrade head

# Docker network
docker compose config --quiet
docker network inspect project_network
```

- [ ] Migration 0003 sukses di `global_postgresql`
- [ ] Model constraints (unique lowercase username, role check) terbukti di Postgres
- [ ] Full suite `pytest -q` hijau (unit+contract+integration)
- [ ] `project_network` terhubung ke `global_postgresql`

---

## 16. Roadmap TDD — 5 Slice (Eksekusi Setelah Dokumen Ini)

```
Slice 1: Model + Migrasi + Password Validator
  -> idp_pegawai/models/idp_user.py + 0003 + security/password.py + tests

Slice 2: Captcha Service (lokal image + Redis TTL)
  -> idp_pegawai/security/captcha.py + tests

Slice 3: Auth Service + Routes Login/Logout + Lockout + Sanitasi
  -> services/auth_service.py + api/auth.py + ui/login.html + tests

Slice 4: Rate Limiter + Decorators login_required/role_required
  -> security/middleware (extend) + access/guards (reuse) + tests

Slice 5: CLI create-admin + /admin/users (admin only) + Hardening headers
  -> operations/create_admin.py + api/admin_users.py + tests
```

Tiap slice: **RED → GREEN → REFACTOR → REGRESSION → EVIDENCE (Postgres) → COMMIT** kecil.

---

## 17. Risiko & Mitigasi

| Risiko | Mitigasi |
|---|---|
| Brute force tanpa captcha | Captcha selalu tampil + rate limiter 2 lapis |
| XSS via username | `sanitize_text()` + Jinja autoescape + CSP |
| Lupa password admin pertama | CLI `create-admin` idempotent, bisa di-run ulang |
| Redis down | Fallback session + log warning, fail-closed (tolak login) |
| Password lemah | Validator 12 + 4 kategori, pesan bahasa Indonesia |
| Username enumeration | Pesan error generik |

---

## 18. Ringkasan Keputusan (Tabel Beku)

```
RBAC          = tipis 2 role (admin/operator) — mapping catalog existing
Captcha       = lokal captcha+Pillow, selalu tampil, Redis TTL 5m, sekali pakai
Password      = 12 char + upper/lower/digit/symbol + cek username
Rate limiter  = per-IP 10/menit (429) + per-username 5/15m lockout
Sanitasi      = sanitize_text + autoescape + CSRF + headers
CLI           = flask create-admin --username --password --role (idempotent)
Migrasi       = 0003_create_idp_users.py (forward, jangan ubah 0001/0002)
Library baru  = captcha==0.7.0 + Pillow==11.1.0 (lainnya sudah ada)
Evidence      = PostgreSQL global_postgresql + project_network + pytest
```

Status akhir: **BEKU untuk implementasi TDD**. Perubahan butuh addendum dokumen baru.

