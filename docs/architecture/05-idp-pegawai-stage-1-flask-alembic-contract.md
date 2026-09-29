# 05 - IDP Pegawai Stage 1 Flask + Alembic Contract

Status: Draft contract brainstorming
Project: kumjabar_ecosystem
Date: 2026-08-26

## 1. Tujuan

Dokumen ini mengunci rancangan **Tahap 1 - Contract & Seed** untuk IDP Pegawai dengan pendekatan implementasi yang dekat ke pola Flask:

- Flask application factory;
- SQLAlchemy ORM;
- Alembic migration/versioning;
- PostgreSQL sebagai database utama;
- Admin UI server-rendered ringan dengan Tailwind minimal;
- Internal API kecil untuk kebutuhan lookup/sync awal.

Tahap 1 belum membangun import pipeline, access grant, audit detail, sync Keycloak penuh, atau delta feed consumer. Fokusnya adalah membuat pondasi identitas ASN dan organisasi yang rapi, bisa dimigrasikan, bisa di-seed, dan mudah dikonsumsi oleh tahap berikutnya. Update 2026-08-27: IDP menjadi source of truth pada tingkat field untuk identitas, eligibility/status, identity link, dan afiliasi organisasi; jabatan serta historinya tetap milik modul kepegawaian seperti `s1-jabar`. Response read-only Tahap 1 perlu mengenalkan metadata freshness/hash hanya untuk field milik IDP, lalu dipertajam pada dokumen 08-09.

## 2. Kesimpulan Stack: Flask Layak untuk IDP Pegawai

Untuk IDP Pegawai, rekomendasi tahap awal adalah **Flask + SQLAlchemy + Alembic + PostgreSQL**.

Alasan:

1. **Scope IDP Pegawai lebih cocok sebagai backoffice/service kecil**  
   Fitur awalnya adalah master data, validasi, import, sync worker, dan Admin UI sederhana. Ini tidak membutuhkan framework besar.

2. **UI operator bisa sederhana dan server-rendered**  
   Admin Kepegawaian butuh halaman list, detail, upload, preview error, dan tombol apply. Flask + Jinja + Tailwind cukup. Tidak perlu SPA berat di fase awal.

3. **SQLAlchemy + Alembic kuat untuk schema contract**  
   Kita butuh partial unique index, JSONB, check constraint, FK, dan migration history. Alembic cocok untuk menjaga kontrak DB tetap eksplisit.

4. **Python unggul untuk import dan normalisasi data**  
   Tahap 2 nanti akan banyak memakai parsing CSV/XLSX, validasi row, normalisasi tanggal/email, dan error workbook. Ekosistem Python lebih enak untuk area ini.

5. **Internal API tetap bisa cepat**  
   Untuk lookup pegawai by email/uuid dan endpoint sync kecil, Flask sudah cukup cepat jika query/index benar. Bottleneck utamanya biasanya database dan network ke Keycloak, bukan framework.

Perbandingan singkat:

| Opsi | Cocok | Kelebihan | Kekurangan untuk IDP Pegawai |
| --- | --- | --- | --- |
| Flask | backoffice kecil, service internal, UI ringan, import pipeline | sederhana, fleksibel, Alembic natural, Python data tooling kuat | perlu disiplin struktur agar tidak jadi `app.py` besar |
| FastAPI | API-first, async, OpenAPI kuat | validasi request bagus, docs otomatis | server-rendered Admin UI tidak senyaman Flask; async belum jadi kebutuhan utama |
| Laravel Lite | konsisten dengan ekosistem Laravel | developer PHP mudah adaptasi, Blade enak | import/sync/data normalization lebih berat; service IDP jadi kurang independen dari aplikasi layanan |

Keputusan desain: **gunakan Flask, tetapi jangan gaya script kecil. Pakai struktur service-layer yang disiplin.**

## 3. Boundary Tahap 1

### 3.1 Yang Masuk Tahap 1

Tahap 1 mencakup:

1. schema inti:
   - `org_units`;
   - `pegawai`;
   - `pegawai_org_assignments`;
   - `pegawai_identity_links`.
2. Alembic migration pertama untuk membuat schema;
3. seed awal `org_units` berdasarkan kontrak Kanwil Jabar;
4. repository/service dasar untuk membaca data;
5. Admin UI read-only/list minimal;
6. Internal API read-only minimal untuk lookup;
7. test/verification schema dan seed.

### 3.2 Yang Belum Masuk Tahap 1

Tahap 1 belum mencakup:

- upload/import CSV/XLSX;
- `import_batches` dan `import_rows`;
- `access_grants`;
- `audit_logs` penuh;
- sync worker Keycloak;
- delta feed/cursor consumer sync penuh;
- hardening final reverse proxy production;
- role/capability UI kompleks;
- public exposure.

Namun field dasar seperti timestamp, soft delete, status, dan metadata tetap disiapkan dari awal agar tahap berikutnya tidak perlu rombak besar.

## 4. Flask Application Shape

Struktur konseptual repo IDP Pegawai:

```text
kumjabar-sso/idp-pegawai/
├── app/
│   ├── __init__.py              # create_app factory
│   ├── config.py                # config object/env
│   ├── extensions.py            # db, migrate, login/oidc, csrf
│   ├── models/
│   │   ├── base.py              # Base mixins + naming convention
│   │   ├── org_unit.py
│   │   ├── pegawai.py
│   │   ├── pegawai_org_assignment.py
│   │   └── pegawai_identity_link.py
│   ├── repositories/
│   │   ├── org_unit_repository.py
│   │   └── pegawai_repository.py
│   ├── services/
│   │   ├── org_unit_service.py
│   │   ├── pegawai_service.py
│   │   └── seed_org_units_service.py
│   ├── blueprints/
│   │   ├── admin/
│   │   │   ├── routes.py
│   │   │   └── templates/
│   │   └── internal_api/
│   │       └── routes.py
│   ├── static/
│   │   └── css/app.css          # Tailwind compiled output
│   └── templates/
├── migrations/
│   ├── env.py
│   └── versions/
├── seeds/
│   └── org_units.v1.yaml
├── tests/
│   ├── test_schema_constraints.py
│   ├── test_org_units_seed.py
│   └── test_internal_api.py
└── pyproject.toml
```

Prinsip:

- route hanya mengatur HTTP/UI;
- service mengatur business rule;
- repository mengatur query;
- model hanya representasi data + helper domain kecil;
- migration ditinjau manual, jangan sepenuhnya percaya autogenerate.

## 5. Database dan Alembic Convention

### 5.1 Database Ownership

Rekomendasi awal:

```text
Database name konseptual: kumjabar_idp_pegawai
Schema PostgreSQL: public
Alembic version table: alembic_version_idp_pegawai
```

Alasan memakai database terpisah dengan schema `public`:

- boundary IDP Pegawai lebih jelas;
- backup/restore lebih mudah;
- permission database lebih mudah dibatasi;
- tidak mencampur tabel aplikasi layanan.

Jika suatu saat dipaksa memakai satu database besar, alternatifnya:

```text
Database: kumjabar_platform
Schema: idp_pegawai
Alembic version table: idp_pegawai.alembic_version
```

Namun default yang lebih bersih untuk service ini adalah database sendiri.

### 5.2 Extension dan Tipe PostgreSQL

Migration pertama perlu mempertimbangkan:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

Dipakai untuk:

```sql
gen_random_uuid()
```

Tipe penting:

| Kebutuhan | Tipe PostgreSQL | SQLAlchemy |
| --- | --- | --- |
| PK internal | `bigint generated by default as identity` | `BigInteger + Identity` |
| UUID publik | `uuid default gen_random_uuid()` | `postgresql.UUID(as_uuid=True)` |
| timestamp | `timestamptz` | `DateTime(timezone=True)` |
| metadata fleksibel | `jsonb` | `postgresql.JSONB` |
| email lookup | `varchar` normalized lowercase | `String` + service normalization |

### 5.3 Naming Convention Constraint

SQLAlchemy metadata sebaiknya memakai naming convention agar Alembic diff stabil:

```python
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

### 5.4 Enum Strategy

Jangan memakai PostgreSQL native enum dulu. Pakai `varchar` + `CHECK constraint` agar perubahan lifecycle lebih mudah dimigrasikan.

Check value tahap 1:

```text
unit_type: kanwil, divisi, bidang, bagian, pokja, tim
status_pegawai: aktif, mutasi_keluar, pensiun, nonaktif, meninggal
assignment_type: primary, additional
identity_provider: keycloak, google, microsoft, local
```

## 6. Mixin Standar Model

Semua core table tahap 1 memakai pola:

| Field | Keterangan |
| --- | --- |
| `id` | bigint PK internal untuk ORM/join efisien |
| `uuid` | UUID public/stable untuk integrasi lintas sistem |
| `metadata` | JSONB default `{}` untuk source snapshot/atribut tambahan |
| `created_at` | timestamptz default `now()` |
| `updated_at` | timestamptz default `now()`, update otomatis dari ORM |
| `deleted_at` | soft delete nullable bila entity utama |

Catatan naming Python:

- kolom database bisa bernama `metadata`, tetapi di SQLAlchemy declarative biasanya `metadata` adalah reserved attribute;
- di model Python gunakan attribute `meta`, tetapi nama kolom tetap `metadata`:

```python
meta = sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
```

## 7. Tabel `org_units`

Fungsi: source of truth struktur organisasi internal yang disinkronkan ke Keycloak group dan dikirim sebagai actor attribute ke aplikasi consumer.

### 7.1 Kolom

| Kolom | Tipe | Wajib | Catatan |
| --- | --- | --- | --- |
| `id` | bigint identity PK | ya | PK internal ORM |
| `uuid` | uuid | ya | default `gen_random_uuid()` atau deterministic seed UUID |
| `parent_id` | bigint FK `org_units.id` | tidak | parent-child tree |
| `code` | varchar(80) | ya | kode stabil, contoh `TUM_TI` |
| `slug` | varchar(120) | ya | segment path, contoh `ti` |
| `name` | varchar(255) | ya | nama lengkap unit |
| `short_name` | varchar(120) | tidak | contoh `TI`, `AHU` |
| `unit_type` | varchar(40) | ya | check constraint |
| `level` | integer | ya | kedalaman tree |
| `path` | varchar(500) | ya | `/kanwil-jabar/tum/ti` |
| `keycloak_group_path` | varchar(500) | ya | `/pegawai/kanwil-jabar/tum/ti` |
| `sort_order` | integer | ya | urutan UI |
| `is_active` | boolean | ya | default true |
| `effective_from` | date | tidak | awal berlaku |
| `effective_to` | date | tidak | akhir berlaku |
| `metadata` | jsonb | ya | default `{}`; bukan jalur penyimpanan jabatan/PLT/PLH |
| `created_at` | timestamptz | ya | default `now()` |
| `updated_at` | timestamptz | ya | default `now()` |
| `deleted_at` | timestamptz | tidak | soft delete |

### 7.2 Constraint dan Index

```text
pk_org_units(id)
unique(uuid)
unique(code) where deleted_at is null
unique(path) where deleted_at is null
unique(keycloak_group_path) where deleted_at is null
index(parent_id)
index(unit_type)
index(is_active)
index(level)
check(unit_type in ...)
check(level >= 0)
check(path like '/%')
check(keycloak_group_path like '/pegawai/%')
check(effective_to is null or effective_from is null or effective_to >= effective_from)
```

### 7.3 Invariant Service

Rule yang dijaga di service/seed:

- `parent_id=null` hanya untuk root `KANWIL_JABAR`;
- `path` dibentuk dari parent path + slug;
- `keycloak_group_path` = `/pegawai` + `path`;
- `code` tidak berubah setelah dipakai aplikasi consumer;
- rename unit boleh mengubah `name`/`short_name`, bukan `code`.

## 8. Tabel `pegawai`

Fungsi: source of truth identitas ASN internal (PNS/PPPK), lifecycle/status, dan eligibility akses internal; bukan source jabatan.

### 8.1 Kolom

| Kolom | Tipe | Wajib | Catatan |
| --- | --- | --- | --- |
| `id` | bigint identity PK | ya | PK internal |
| `uuid` | uuid | ya | claim `pegawai_uuid` |
| `nip` | varchar(18) | ya | identitas ASN PNS/PPPK; tepat 18 karakter digit |
| `nama_lengkap` | varchar(255) | ya | nama tanpa gelar bila memungkinkan |
| `gelar_depan` | varchar(80) | tidak | opsional |
| `gelar_belakang` | varchar(120) | tidak | opsional |
| `email_dinas` | varchar(255) | tidak | email resmi |
| `email_dinas_normalized` | varchar(255) | tidak | lowercase trim |
| `email_google` | varchar(255) | tidak | email Google broker |
| `email_google_normalized` | varchar(255) | tidak | lowercase trim |
| `no_hp` | varchar(50) | tidak | opsional, jangan wajib awal |
| `primary_org_unit_id` | bigint FK `org_units.id` | tidak | unit utama aktif |
| `status_pegawai` | varchar(40) | ya | lifecycle wajib explicit; check constraint |
| `is_active` | boolean | ya | eligibility yang diturunkan service dari status |
| `status_reason` | text | tidak | alasan perubahan status |
| `status_effective_at` | date | tidak | tanggal berlaku status |
| `keycloak_user_id` | varchar(120) | tidak | ID user Keycloak |
| `metadata` | jsonb | ya | default `{}`; source snapshot identitas, bukan jabatan/PLT/PLH |
| `created_at` | timestamptz | ya | default `now()` |
| `updated_at` | timestamptz | ya | default `now()` |
| `deleted_at` | timestamptz | tidak | soft delete |

### 8.2 Constraint dan Index

```text
pk_pegawai(id)
unique(uuid)
unique(nip) where deleted_at is null
check(nip ~ '^[0-9]{18}$')
unique(email_dinas_normalized) where email_dinas_normalized is not null and deleted_at is null
unique(email_google_normalized) where email_google_normalized is not null and deleted_at is null
index(primary_org_unit_id)
index(status_pegawai)
index(is_active)
index(keycloak_user_id)
check(status_pegawai in ...)
check(is_active = (status_pegawai = 'aktif'))
check(is_active = false or primary_org_unit_id is not null)
```

Catatan:

- `nip` wajib, disimpan sebagai string `varchar(18)`, dan harus cocok regex `^[0-9]{18}$`;
- scope IDP hanya ASN PNS dan PPPK; Non-ASN/PPNPN tidak masuk;
- `is_active` diturunkan deterministik dari lifecycle: `true` hanya dan selalu ketika `status_pegawai='aktif'`;
- pegawai aktif sebaiknya wajib punya `primary_org_unit_id`;
- pegawai nonaktif/mutasi/pensiun jangan dihapus;
- email asli tetap disimpan, lookup memakai kolom normalized;
- service wajib menormalisasi email sebelum insert/update.

## 9. Tabel `pegawai_org_assignments`

Fungsi: menyimpan unit utama secara historis dan afiliasi unit organisasi tambahan. Tabel ini bukan tempat jabatan, PLT, atau role operator/admin aplikasi.

### 9.1 Kolom

| Kolom | Tipe | Wajib | Catatan |
| --- | --- | --- | --- |
| `id` | bigint identity PK | ya | PK internal |
| `uuid` | uuid | ya | identitas assignment |
| `pegawai_id` | bigint FK `pegawai.id` | ya | pegawai |
| `org_unit_id` | bigint FK `org_units.id` | ya | unit terkait |
| `assignment_type` | varchar(40) | ya | `primary` atau `additional`; afiliasi organisasi saja |
| `is_primary` | boolean | ya | default false |
| `is_active` | boolean | ya | default true |
| `started_at` | date | tidak | mulai berlaku |
| `ended_at` | date | tidak | selesai berlaku |
| `metadata` | jsonb | ya | default `{}`; metadata afiliasi organisasi, bukan jabatan/PLT/PLH |
| `created_at` | timestamptz | ya | default `now()` |
| `updated_at` | timestamptz | ya | default `now()` |
| `deleted_at` | timestamptz | tidak | soft delete |

### 9.2 Constraint dan Index

```text
pk_pegawai_org_assignments(id)
unique(uuid)
index(pegawai_id)
index(org_unit_id)
index(assignment_type)
index(is_active)
unique active primary assignment per pegawai:
  unique(pegawai_id) where is_primary = true and is_active = true and deleted_at is null
unique active same assignment:
  unique(pegawai_id, org_unit_id, assignment_type) where is_active = true and deleted_at is null
check(assignment_type in ...)
check(ended_at is null or started_at is null or ended_at >= started_at)
check(is_primary = false or assignment_type = 'primary')
```

### 9.3 Invariant Service

- `pegawai.primary_org_unit_id` adalah shortcut unit utama saat ini;
- assignment `primary` aktif harus selaras dengan `pegawai.primary_org_unit_id`;
- assignment tambahan tidak boleh mengubah primary unit;
- histori assignment lama ditutup dengan `ended_at`/`is_active=false`, bukan dihapus.

## 10. Tabel `pegawai_identity_links`

Fungsi: menghubungkan pegawai dengan identity provider seperti Keycloak, Google, Microsoft, atau local bootstrap.

### 10.1 Kolom

| Kolom | Tipe | Wajib | Catatan |
| --- | --- | --- | --- |
| `id` | bigint identity PK | ya | PK internal |
| `uuid` | uuid | ya | identitas link |
| `pegawai_id` | bigint FK `pegawai.id` | ya | pegawai |
| `provider` | varchar(40) | ya | check constraint |
| `provider_subject` | varchar(255) | tidak | subject/id provider |
| `email` | varchar(255) | tidak | email saat linking |
| `email_normalized` | varchar(255) | tidak | lowercase trim |
| `email_verified` | boolean | ya | default false |
| `is_active` | boolean | ya | default true |
| `linked_at` | timestamptz | tidak | waktu link |
| `last_seen_at` | timestamptz | tidak | login terakhir |
| `metadata` | jsonb | ya | default `{}` |
| `created_at` | timestamptz | ya | default `now()` |
| `updated_at` | timestamptz | ya | default `now()` |

### 10.2 Constraint dan Index

```text
pk_pegawai_identity_links(id)
unique(uuid)
unique(provider, provider_subject) where provider_subject is not null
unique(provider, email_normalized) where email_normalized is not null and is_active = true
index(pegawai_id)
index(provider)
index(email_normalized)
index(is_active)
check(provider in ...)
```

Catatan:

- Google login pegawai hanya dianggap pegawai jika `email_verified=true`, link aktif, dan pegawai aktif;
- jangan percaya domain email saja;
- perubahan email/link harus menjadi audit event pada tahap 3.

## 11. Seed `org_units` Versi 1

Tahap 1 harus menyediakan seed awal 21 unit organisasi.

### 11.1 Format Seed

Disarankan file:

```text
seeds/org_units.v1.yaml
```

Field:

```text
code
parent_code
slug
name
short_name
unit_type
level
path
keycloak_group_path
sort_order
is_active
```

Untuk UUID seed ada dua opsi:

1. **Generated once lalu disimpan di seed file**  
   Cocok jika ingin UUID benar-benar stabil lintas environment.

2. **Deterministic UUID v5 dari namespace + code**  
   Cocok jika ingin seed ringkas tetapi tetap menghasilkan UUID stabil.

Rekomendasi: gunakan **deterministic UUID v5** untuk `org_units` karena `code` stabil dan seed bisa idempotent.

### 11.2 Canonical Codes

```text
KANWIL_JABAR
DIV_YANKUM
YANKUM_AHU
YANKUM_KI
DIV_P3H
P3H_SUNCANG
P3H_BSK
P3H_JDIH
P3H_BANKUM
TUM
TUM_PPL
TUM_KEPEGAWAIAN
TUM_HUMAS
TUM_TI
TUM_KEUANGAN
TUM_BMN
TUM_SEKRETARIAT
TUM_PROTOKOLER
TUM_RB_KERJASAMA
TUM_KEARSIPAN
TUM_PENGADUAN
```

Rows lengkap mengikuti kontrak pada `03-keycloak-matrix-and-org-unit-seed.md`.

### 11.3 Seed Behavior

Seed harus idempotent:

```text
for each seed row:
  find org_units by code where deleted_at is null
  if not exists: insert
  if exists: update mutable fields
```

Mutable fields:

```text
parent_id
slug
name
short_name
unit_type
level
path
keycloak_group_path
sort_order
is_active
effective_from
effective_to
metadata
```

Immutable/stable fields:

```text
code
uuid
```

Jika `code` berubah, treat sebagai unit baru atau migration khusus, bukan update biasa.

## 12. Minimal Admin UI Tahap 1

UI cukup kecil:

```text
GET /admin/
  Dashboard ringkas: jumlah unit, jumlah pegawai, status database.

GET /admin/org-units
  Tree/list org unit, filter active/unit_type.

GET /admin/org-units/<uuid>
  Detail org unit dan child units.

GET /admin/pegawai
  List pegawai, filter status/org unit/email.

GET /admin/pegawai/<uuid>
  Detail pegawai, primary unit, assignments, identity links.
```

Teknologi UI:

- Jinja template;
- Tailwind compiled CSS;
- HTMX boleh dipakai nanti untuk interaksi kecil, tapi jangan wajib di Tahap 1;
- CDN Tailwind boleh untuk prototype lokal, tetapi production sebaiknya compiled asset agar CSP lebih aman.

## 13. Minimal Internal API Tahap 1

Internal API read-only:

```text
GET /internal/org-units
GET /internal/org-units/<uuid>
GET /internal/pegawai/<uuid>
GET /internal/pegawai/by-email?email=...
```

Response envelope konseptual:

```json
{
  "data": {},
  "meta": {
    "request_id": "..."
  }
}
```

Error envelope:

```json
{
  "error": {
    "code": "not_found",
    "message": "Pegawai tidak ditemukan"
  },
  "meta": {
    "request_id": "..."
  }
}
```

Catatan keamanan:

- endpoint `/internal/*` tetap dianggap private network;
- jangan diekspos publik oleh gateway;
- authentication internal API bisa dimatangkan pada tahap berikutnya, tetapi route boundary disiapkan sejak awal.

## 14. Alembic Revision Plan Tahap 1

Detail draft Alembic konseptual diturunkan lagi di `06-idp-pegawai-stage-1-alembic-draft.md`. Dokumen 06 tetap bersifat brainstorming arsitektur, bukan migration `.py` siap jalan.

### 14.1 Revision `0001_create_idp_pegawai_core`

Isi:

1. `CREATE EXTENSION IF NOT EXISTS pgcrypto`;
2. create table `org_units`;
3. create table `pegawai`;
4. create table `pegawai_org_assignments`;
5. create table `pegawai_identity_links`;
6. create indexes, partial unique indexes, and check constraints.

### 14.2 Seed Tidak Wajib Masuk Alembic

Rekomendasi:

- Alembic mengurus struktur schema;
- seed mengurus data referensi awal melalui service/CLI idempotent;
- seed punya versi file sendiri (`org_units.v1.yaml`).

Alasan:

- organisasi bisa berubah sebagai data operasional;
- rollback migration tidak selalu berarti rollback data organisasi;
- seed service lebih mudah dites dan diulang.

Namun bootstrap environment kosong boleh menjalankan urutan:

```text
flask db upgrade
flask seed org-units --file seeds/org_units.v1.yaml
```

## 15. Test dan Verification Tahap 1

Acceptance criteria:

- Alembic migration berhasil `upgrade head` di PostgreSQL;
- Alembic migration bisa `downgrade base` di database test;
- partial unique index bekerja:
  - duplicate `org_units.code` aktif ditolak;
  - duplicate email normalized pegawai aktif ditolak;
  - soft deleted row tidak memblokir insert baru jika memang diizinkan;
- check constraint bekerja:
  - `unit_type` invalid ditolak;
  - `status_pegawai` invalid ditolak;
  - setiap kombinasi `status_pegawai`/`is_active` yang tidak sama dengan aturan derivasi (`aktif -> true`, status lain -> false) ditolak;
- seed `org_units.v1.yaml` menghasilkan 21 rows;
- seed bisa dijalankan dua kali tanpa duplikasi;
- `keycloak_group_path` semua dimulai dengan `/pegawai/`;
- Admin UI list org units bisa membaca tree;
- Internal API lookup by email memakai normalized email.

## 16. Risiko dan Mitigasi

| Risiko | Dampak | Mitigasi |
| --- | --- | --- |
| Flask dibuat terlalu bebas | code sulit dirawat | wajib app factory + blueprint + service/repository |
| Tailwind CDN terbawa ke production | CSP/security kurang rapi | compile Tailwind untuk production |
| Alembic autogenerate tidak menangkap partial index/check detail | schema tidak sesuai kontrak | review manual migration |
| email duplicate karena case/space | lookup pegawai salah | normalized email column + unique partial index |
| primary unit dan assignment primary tidak sinkron | token claims salah | invariant di service + test |
| seed berubah tanpa versi | environment berbeda-beda | versioned seed file + idempotent seeder |
| JSONB dipakai untuk struktur utama | query/sync/ABAC sulit | struktur organisasi tetap relasional |

## 17. Keputusan Tahap 1 yang Diusulkan

1. IDP Pegawai memakai **Flask + SQLAlchemy + Alembic**.
2. Admin UI awal memakai **Jinja + Tailwind minimal**.
3. Database service memakai **PostgreSQL**, default database terpisah `kumjabar_idp_pegawai`.
4. Tahap 1 hanya mengimplementasikan core contract dan seed:
   - `org_units`;
   - `pegawai`;
   - `pegawai_org_assignments`;
   - `pegawai_identity_links`.
5. Seed `org_units` dibuat idempotent dan versioned.
6. Import, access grant, audit penuh, dan sync Keycloak masuk tahap berikutnya sesuai roadmap 5 tahap.
