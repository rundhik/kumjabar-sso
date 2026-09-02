# Sprint 1-5 Execution Plan — IDP Pegawai

Tanggal: 2026-09-08
Status: Sprint 2–3 closed locally; Sprint 4/5 evidence next

## Baseline

- Runtime package resmi: `idp-pegawai/idp_pegawai/`.
- Tidak ada compatibility symlink `idp_pegawai` di root.
- Compose service: `kumjabar_idp` dengan `PYTHONPATH=/usr/src/app/idp-pegawai`.
- Docker regression terakhir: `216 passed, 1 warning`.
- Host PostgreSQL integration tidak dijadikan evidence karena `global_postgresql` hanya tersedia di Docker network.

## Sprint 1 — Runtime baseline

Status: hampir selesai.

- [x] Package move ke `idp-pegawai/idp_pegawai`.
- [x] Compose memakai package path resmi.
- [x] Migration + seed startup sequence.
- [ ] Evidence PostgreSQL host-independent disimpan sebagai command Docker canonical.

## Sprint 2 — IDP Pegawai CRUD dan UI

Status: **closed — local Docker evidence GREEN**.

- [x] Contract API organisasi: list/detail/create/update/deactivate.
- [x] Contract API pegawai: list/detail/create/update/deactivate.
- [x] Service layer menjaga lifecycle, assignment primary, dan soft delete.
- [x] UI organisasi dan pegawai memakai API/service resmi, bukan direct DB dari browser.
- [x] Deny-by-default mutation dan capability guard.
- [x] Flasgger-compatible endpoint docstrings untuk mutation CRUD.
- [x] Regression Docker: `223 passed, 2 skipped, 1 warning`.
- [x] Regression active → nonaktif: status dan `is_active` tetap konsisten.
- [x] Invalid organization reference pada create/update ditolak aman sebagai 404.

Evidence Sprint 2 terbaru: targeted CRUD/lifecycle/read contracts `17 passed`; full Docker suite `223 passed, 2 skipped, 1 warning in 9.70s`, dijalankan dengan `DB_NAME=db_sso_test` dan tanpa menyentuh `db_sso`.

## Sprint 3 — Import HTTP/UI vertical slice

Status: **closed locally — Docker evidence GREEN; browser/manual rehearsal remains user review**.

- [x] Intake, mapping, normalization, validation, dry-run, error workbook, atomic apply, outbox.
- [x] Bekukan contract HTTP upload/status/mapping/dry-run/preview/approve/apply.
- [x] Tampilkan state transition, reset batch workflow, dan error catalog humanis di UI.
- [x] Dokumentasi OpenAPI/Flasgger-compatible endpoint import.
- [x] Contract regression import + UI: `18 passed`.
- [ ] Browser/manual rehearsal tanpa membocorkan raw workbook, token, atau PII — menunggu review manual user.

Evidence Sprint 3 terbaru: targeted import/UI contracts `18 passed in 7.16s`; full Docker suite `225 passed, 2 skipped, 1 warning in 9.09s`, dengan `DB_NAME=db_sso_test`.

## Sprint 4 — Keycloak projection

- [x] Desired-state resolver, identity link projection, adapter policy, reconciliation harness.
- [ ] Pin image/version dan environment non-production.
- [ ] Evidence HTTPS, JWKS, PKCE, state/nonce, audience/azp, rotation.
- [ ] Reconciliation drift dan rollback runbook.

## Sprint 5 — Consumer, OIDC, gateway, operations

- [x] Canonical profile/projector, cursor, freshness, OIDC validator, readiness artifacts.
- [ ] Runtime consumer registration/change-log rehearsal.
- [ ] Gateway private-route deny tests dan TLS/proxy evidence.
- [ ] Bootstrap cutoff, replay window, conflict, suspension/reactivation rehearsal.
- [ ] Privacy scan runtime logs/metrics/traces.

## Urutan eksekusi cepat

1. Review manual Sprint 2–3 oleh user menggunakan checklist di bawah.
2. Tutup item yang gagal dari review manual dan jalankan regression ulang.
3. Sprint 4/5 operational evidence dan runbook.

## Checklist review manual user — Sprint 2–3

### A. Pegawai

- [ ] `/ui/pegawai` menampilkan pegawai aktif dan nonaktif.
- [ ] Card status menampilkan total Aktif, Nonaktif, Mutasi keluar, Pensiun, dan Meninggal.
- [ ] Tambah pegawai valid berhasil dan muncul setelah reload.
- [ ] Tambah pegawai aktif tanpa unit aktif ditolak dengan pesan yang jelas.
- [ ] Edit nama/email/unit berhasil.
- [ ] Edit aktif → nonaktif berhasil; status tetap terlihat di daftar.
- [ ] Edit nonaktif → aktif hanya berhasil jika unit utama aktif.
- [ ] NIP tidak dapat diubah saat edit.
- [ ] Tombol Nonaktifkan hanya muncul untuk pegawai aktif.

### B. Organisasi

- [ ] Setiap field modal memiliki helper text yang mudah dipahami.
- [ ] Tambah unit valid berhasil.
- [ ] Path dan Keycloak group path yang tidak konsisten ditolak.
- [ ] Parent/unit tidak ditemukan menghasilkan pesan validasi yang jelas.
- [ ] Setelah error, membuka Tambah unit mereset field dan pesan error lama.
- [ ] Edit unit berhasil.
- [ ] Nonaktifkan unit tidak menghapus record dari database.

### C. Import

- [ ] Upload file valid menampilkan status `received`.
- [ ] Upload file baru mereset preview, summary, tombol Apply, dan status batch lama.
- [ ] Mapping valid lanjut ke dry-run.
- [ ] Mapping kolom salah menampilkan pesan humanis dan tidak membuka Apply.
- [ ] Dry-run menampilkan jumlah baru, berubah, tidak berubah, dan ditolak.
- [ ] Row error menampilkan nomor baris, kolom, dan alasan.
- [ ] Preview menampilkan kolom yang dipakai dan jumlah data.
- [ ] Approve mengubah status menjadi `ready_to_apply`.
- [ ] Apply menyimpan data dan menonaktifkan tombol Apply ulang.
- [ ] Download error menghasilkan workbook error tanpa token/storage key/raw payload di UI.

### D. Bukti manual yang perlu dikirim balik

Catat untuk setiap masalah: halaman, langkah, payload/file sintetis (tanpa PII), hasil yang diharapkan, hasil aktual, dan screenshot bila perlu. Jangan kirim password, token, isi workbook asli, atau data pegawai nyata.

Setelah checklist ini GREEN, kita lanjut ke Sprint 4/5 evidence. Production tetap BLOCKED sampai evidence staging/runtime eksternal selesai.

## Gate

Tidak lanjut ke staging/production sebelum Docker full suite GREEN dan evidence external yang relevan tersedia. Tidak mengubah Keycloak production, gateway production, DNS, TLS, atau database secara destruktif.
