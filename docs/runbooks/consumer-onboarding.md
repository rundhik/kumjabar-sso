# Runbook onboarding consumer

> Artefak prosedur; tidak mengaktifkan deployment, DNS, atau TLS.

## Prasyarat dan persetujuan

1. Catat `consumer_code`, pemilik layanan, tujuan pemrosesan, contract/profile version,
   scope field, retention, dan kontak on-call.
2. Pastikan persetujuan security/privacy dan network owner tersedia.
3. Buat credential melalui secret manager; jangan menaruh secret, token, atau cursor
   key di database, konfigurasi Git, tiket, atau log.
4. Pastikan akses hanya ke private ingress, dengan audience `idp-pegawai-internal`
   dan scope minimum `feed:read`.

## Sandbox dan bootstrap

1. Jalankan contract test di sandbox dan verifikasi public ingress menolak
   `/internal/`, `/feed/`, dan `/worker/`, termasuk variasi path-prefix.
2. Lakukan bootstrap dry-run dengan cutoff sequence dan bounded paginated response.
3. Validasi setiap halaman sebelum upsert; checkpoint dan data harus committed atomik.
4. Jika validasi/commit gagal, ulangi halaman yang sama tanpa memajukan checkpoint.
   Cursor invalid atau cutoff expired menghentikan proses—jangan reset diam-diam.
5. Setelah seluruh snapshot lulus, tandai bootstrap selesai lalu mulai delta dari
   sequence setelah cutoff.

## Readiness dan handover

Catat bukti TLS upstream terverifikasi, trusted proxy allowlist, rate/size/timeout
bounds, dashboard lag/checkpoint, alert, rollback/rebootstrap drill, dan on-call.
Aktivasi production memerlukan evidence gate serta otorisasi terpisah.

## Pemulihan singkat

Credential gagal: suspend pull dan rotasi/review. Gap atau replay expired: hentikan
pull baru dan lakukan controlled bootstrap. Jangan mengubah field domain-owned consumer.
