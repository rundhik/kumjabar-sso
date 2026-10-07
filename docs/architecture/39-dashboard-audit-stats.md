# 39 — Dashboard Audit & Statistik

## Tujuan
`/ui` (Ringkasan) menampilkan statistik terkurasi untuk admin & operator:

| Kartu | Sumber | Keterangan |
|---|---|---|
| Pegawai | `pegawai` via `PEGAWAI_REPOSITORY.list_active_snapshot_scope()` | `COUNT` pegawai aktif |
| Organisasi | `org_units` via `ORG_UNIT_REPOSITORY.list_active()` | `COUNT` unit aktif |
| Batch Staging / Applied / Error | `import_batches` | `SELECT status, COUNT(*) GROUP BY status` |
| Sync Keycloak | `keycloak_sync_logs` | `COUNT(*)` — 1 row per `POST /admin/pegawai/sync-keycloak` |
| Request Consumer | `consumer_profile_request_logs` | `COUNT(*)` — 1 row per `GET /idp-pegawai/internal/api/v1/consumer/profile` |

Akses: `Capability.DASHBOARD_VIEW` (admin & operator). Tanpa filter role tambahan untuk MVP.

## Status Implementasi (sudah live)

### Migrasi
`idp-pegawai/migrations/versions/0004_dashboard_audit_logs.py` — forward-only, auto dijalankan `flask db upgrade` saat container start.

```sql
-- keycloak_sync_logs
id              BIGSERIAL PK (Identity)
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
actor_user_id   BIGINT FK -> idp_users(id) NULL
result          VARCHAR(20) NOT NULL  -- success|partial|failed
created_count   INT NOT NULL DEFAULT 0
updated_count   INT NOT NULL DEFAULT 0
skipped_count   INT NOT NULL DEFAULT 0
failed_count    INT NOT NULL DEFAULT 0
total_processed INT NOT NULL DEFAULT 0
detail          JSONB NOT NULL DEFAULT '{}'::jsonb
INDEX (created_at)

-- consumer_profile_request_logs
id              BIGSERIAL PK (Identity)
requested_at    TIMESTAMPTZ NOT NULL DEFAULT now()
consumer_id     VARCHAR(255) NOT NULL  -- azp dari JWT
endpoint        VARCHAR(500) NOT NULL  -- request.path
http_status     INT NULL
latency_ms      INT NULL
pegawai_uuid    UUID NULL
INDEX (requested_at), INDEX (consumer_id)
```

### Penulisan Log
| Event | Lokasi kode | Trigger |
|---|---|---|
| `keycloak_sync_logs` | `idp_pegawai/api/admin.py :: sync_pegawai_to_keycloak()` | Akhir loop sync; best-effort `INSERT`, `rollback` on error, tidak menggagalkan response |
| `consumer_profile_request_logs` | `idp_pegawai/api/profile.py :: profile()` | Setelah `resolve()` sukses; sampling via `CONSUMER_LOG_SAMPLE_RATE` (default 1.0), `request.environ["profile_start_ts"]` untuk latency |

### Pembacaan Dashboard
`idp_pegawai/ui.py :: _dashboard_stats()`:
- Pegawai/organisasi via repository (fallback 0 on exception).
- `import_batches` + 2 tabel audit via `psycopg` + `DATABASE_URL` (fallback psycopg). Per tabel dibungkus `try/except: conn.rollback()` agar dashboard tidak 500 bila tabel belum ada / query gagal.
- Return dict: `{pegawai, organisasi, batch_staging, batch_applied, batch_error, kc_logs, consumer_logs}`

`idp_pegawai/templates/ui/dashboard.html` render 7 kartu grid dari `stats`.

## Cara Verifikasi
```bash
# 1. Cek tabel ada
docker exec global_postgresql psql -U postgres -d db_sso -c "\d keycloak_sync_logs"
docker exec global_postgresql psql -U postgres -d db_sso -c "\d consumer_profile_request_logs"

# 2. Cek angka mentah
docker exec global_postgresql psql -U postgres -d db_sso -c "SELECT status, COUNT(*) FROM import_batches GROUP BY status; SELECT COUNT(*) FROM keycloak_sync_logs; SELECT COUNT(*) FROM consumer_profile_request_logs;"

# 3. Trigger log
curl -X POST http://localhost:9999/admin/pegawai/sync-keycloak -H "Authorization: Bearer <admin_token>"
curl http://localhost:9999/idp-pegawai/internal/api/v1/consumer/profile -H "Authorization: Bearer <consumer_jwt>"

# 4. Buka /ui — kartu Sync Keycloak & Request Consumer harus naik +1
```

## Roadmap (opsional, tunda hingga ada kebutuhan)
- Filter 7/30 hari: `WHERE created_at > now() - interval '7 days'`.
- Retention: `DELETE WHERE created_at < now() - interval '90 days'` (cron).
- Partisi bulanan bila `consumer_profile_request_logs` > 1M rows.
- Full `audit_events` generik (event_type, actor, entity_type, entity_id, payload) — ditunda hingga butuh compliance/forensik; butuh migrasi besar & hook di semua service mutasi.

## Catatan Penting
- Jangan downgrade DB; migrasi forward-only.
- Dashboard harus tetap 200 meski tabel audit kosong — sudah di-handle `try/except + rollback`.
- Consumer log bisa besar — pertimbangkan `CONSUMER_LOG_SAMPLE_RATE < 1.0` bila traffic tinggi.
