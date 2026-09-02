# Runbook incident response gateway dan consumer

> Prosedur terkendali; bukan otorisasi perubahan deployment, DNS, atau TLS.

## Triage dan containment

1. Buat incident ID dan catat waktu, route template, status class, consumer code,
   resource family, serta contract/profile version saja.
2. Jangan mencatat atau menyalin PII, Authorization/Cookie, token, cursor, payload,
   request body, query, atau raw upstream response.
3. Jika public ingress mengekspos route internal/feed/worker, segera deny route di
   gateway policy, isolasikan private ingress, dan pertahankan bukti log ter-redaksi.
4. Jika credential diduga bocor, suspend registration/pull dan lakukan rotasi melalui
   secret manager. Jangan melakukan retry mutation secara buta.

## Diagnosis bounded

- Verifikasi trusted proxy berasal dari explicit allowlist dan forwarded headers
  ditimpa gateway; abaikan header spoofed dari client.
- Verifikasi TLS upstream tetap melakukan certificate/hostname verification.
- Periksa body/header/timeout/rate-limit bounds dan status class, bukan isi payload.
- Untuk consumer lag/gap/cursor invalid: hentikan bootstrap/replay baru, pertahankan
  checkpoint terakhir yang valid, dan pilih replay atau controlled rebootstrap.
- Untuk partial apply: jangan memajukan checkpoint; ulangi hanya operasi yang aman
  dan idempotent setelah review. Mutation memerlukan keputusan operator.

## Pemulihan dan penutupan

1. Pulihkan private route dan credential hanya setelah owner menyetujui evidence.
2. Jalankan contract tests, cek checkpoint continuity, snapshot hash, tombstone, dan
   observability/alert.
3. Dokumentasikan root cause, rentang dampak, tindakan, reviewer, dan evidence hash
   tanpa menyimpan secret atau data sensitif.
4. Tutup incident setelah on-call dan security/privacy owner menyetujui; setiap
   production activation tetap melalui change/evidence gate terpisah.

## Batasan

Tidak ada DNS/TLS certificate change, deployment activation, raw log export, atau
penghapusan snapshot lama sebagai tindakan otomatis dalam runbook ini.
