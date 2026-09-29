# AGENTS.md — kumjabar-sso

## Bahasa dan history
- Komunikasi dengan user menggunakan Bahasa Indonesia.
- Simpan ringkasan setiap respons ke `/home/user/chats/kumjabar-sso/` dengan nama `YYYY-MM-DD_HH-MM-SS-telegram.md`.
- Setiap ringkasan wajib memuat respons assistant di bawah heading `## Respon`.
- Saat memulai sesi, baca file ini dan ringkasan Markdown project yang relevan.

## Workspace dan batasan
- Hanya bekerja pada `/home/user/projects/kumjabar-sso`, kecuali user memberi instruksi eksplisit untuk membaca project lain.
- Jangan mengubah production infrastructure, Keycloak production, gateway, DNS, TLS, atau deployment tanpa otorisasi dan evidence gate terpisah.
- Jangan membaca atau mencetak isi `.env` ke chat, log, commit, atau artefak history.

## Environment dan Docker
- Variable lokal disimpan di `.env`; `.env` tidak boleh di-commit.
- Development/test menggunakan Docker image `python3-base:latest` bila kompatibel.
- PostgreSQL memakai container global `global_postgresql`, database `db_sso`, user `postgres`; password hanya melalui `.env`/secret dan tidak ditulis ke source.
- Container aplikasi harus bergabung ke external Docker network `project_network` agar dapat mengakses `global_postgresql`.
- PostgreSQL nyata adalah evidence correctness; jangan mengganti evidence dengan SQLite.

## Engineering
- Flask application factory tetap tipis, modular, robust, dan mudah diuji.
- Layer: models, repositories (query-only), services (business orchestration), routes/API.
- Ikuti siklus TDD: RED → GREEN → REFACTOR → REGRESSION → EVIDENCE → COMMIT.
- Hindari arbitrary claims, fields, group paths, generic policy DSL, dan remote call di dalam transaksi domain.
- Jangan melanjutkan phase jika full suite gagal atau review gate blocked.
- Generated Python bytecode/cache, virtualenv, build artifacts, dan secrets wajib masuk `.gitignore`.
- Setiap endpoint/API baru wajib dilengkapi dokumentasi OpenAPI/Swagger menggunakan Flasgger yang tersedia pada `python3-base:latest`; dokumentasi tidak boleh membocorkan secret, token, PII, atau payload sensitif.

## Architecture authority
- Dokumen `docs/architecture/*.md` adalah sumber kontrak implementasi.
- PostgreSQL IDP adalah authority identitas ASN dan organisasi.
- Keycloak hanya authentication dan managed projection.
- Consumer hanya menerima curated snapshot/delta dan memiliki checkpoint lokal.
