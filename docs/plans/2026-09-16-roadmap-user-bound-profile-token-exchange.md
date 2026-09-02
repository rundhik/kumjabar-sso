# Roadmap Eksekusi — User-Bound Profile dengan Token Exchange

Tanggal: 2026-09-16
Status: READY TO EXECUTE LOCALLY
Prioritas: tinggi
Pilot: `s1-jabar`

## Tujuan

Menyelesaikan alur production-shaped berikut tanpa static service token dan tanpa custom header subject mentah:

```text
User login OIDC di Keycloak
        ↓
s1-jabar membuat session server-side
        ↓
login OIDC selesai secara mandiri
        ↓
route authorization aplikasi meminta profile pegawai
        ↓
s1-jabar melakukan token exchange/delegation di backend
        ↓
Keycloak menerbitkan token user-bound untuk IDP Pegawai
        ↓
IDP memvalidasi service/client + user identity
        ↓
provider + issuer + provider_subject
        ↓
identity link → pegawai → eligibility
        ↓
pegawai-profile.v1 atau denial authorization
```

## Prinsip yang tidak boleh dilanggar

- IDP Pegawai adalah source of truth pegawai, status, eligibility, identity link, dan unit.
- Keycloak adalah authority autentikasi dan penerbit token.
- Human client dan service/feed client tetap terpisah.
- `s1-feed` tidak boleh dipakai sebagai subject pegawai.
- Tidak ada direct database access dari client.
- Tidak ada `X-User-Subject` mentah yang dipercaya sebagai identity.
- Tidak ada static JWT di `.env` sebagai solusi normal.
- Token tidak boleh berada di browser, localStorage, URL, log, atau artifact.
- Semua perubahan harus lulus targeted test lalu full regression.
- Login OIDC dan pemeriksaan profile/eligibility adalah dua tahap berbeda; kegagalan profile tidak boleh dipetakan sebagai kegagalan login OIDC.
- Session login boleh terbentuk setelah callback OIDC valid, tetapi route aplikasi wajib menolak akses domain sampai profile pegawai tervalidasi sesuai policy.

## Phase 0 — Freeze keputusan arsitektur

- [ ] Bekukan token exchange/delegated token sebagai jalur utama.
- [ ] Tentukan apakah Keycloak lokal mendukung token exchange standar pada versi/image yang dipakai.
- [ ] Tetapkan human client `s1-jabar`/`s1-internal` sesuai konfigurasi aktual.
- [ ] Tetapkan feed client `s1-feed` untuk service authorization.
- [ ] Tetapkan resource audience `idp-pegawai-internal`.
- [ ] Tetapkan scope `profile:read`.
- [ ] Tetapkan claim user-bound yang wajib: `iss`, `sub`, `aud`, `azp`, `exp`, `iat`.
- [ ] Tetapkan apakah token exchange menghasilkan `azp=s1-feed` atau perlu consumer binding server-side yang terdokumentasi.
- [ ] Tolak perubahan kode client sebelum keputusan claim/token final dibekukan.

### Gate Phase 0

```text
[ ] Ada diagram request final.
[ ] Tidak ada custom subject header.
[ ] Tidak ada static service JWT.
[ ] Claim token final tertulis.
[ ] Failure contract tertulis.
```

## Phase 1 — Keycloak local token exchange

- [ ] Pastikan realm `kumjabar` dan issuer final konsisten.
- [ ] Pastikan human client memiliki Authorization Code + PKCE S256.
- [ ] Pastikan `s1-feed` confidential client memiliki service account.
- [ ] Pastikan client scope `profile:read` tersedia.
- [ ] Pastikan audience `idp-pegawai-internal` tersedia.
- [ ] Konfigurasi permission/policy token exchange hanya untuk caller yang disetujui.
- [ ] Batasi target audience/resource hanya `idp-pegawai-internal`.
- [ ] Pastikan token exchange tidak dapat dipakai sebagai impersonation bebas.
- [ ] Uji token exchange dengan secret/token hanya lokal, tanpa mencetak token.
- [ ] Verifikasi metadata token secara redacted: format, issuer, audience, azp, scope, subject presence, expiry.
- [ ] Rotasi credential yang pernah tercetak di chat/log.

### Gate Phase 1

```text
[ ] Token exchange berhasil.
[ ] Token hasil exchange memiliki subject user demo.s1.
[ ] Audience idp-pegawai-internal.
[ ] Scope profile:read.
[ ] Signature/kid ada pada JWKS IDP.
[ ] Expiry masih berlaku.
[ ] Token tidak dicetak.
```

## Phase 2 — IDP Pegawai authorization contract

- [ ] Pisahkan validasi service authorization dan user identity secara eksplisit.
- [ ] Validasi signature/JWKS, issuer, audience, azp, exp/iat, algorithm.
- [ ] Dukung audience JWT string maupun array secara konsisten.
- [ ] Validasi `profile:read`.
- [ ] Lookup `consumer_registrations` berdasarkan consumer/client binding.
- [ ] Tolak registration yang tidak ada, revoked, atau decommissioned.
- [ ] Validasi resource family dan field profile allowlist.
- [ ] Resolve identity hanya dari claim token user-bound: `provider + iss + sub`.
- [ ] Jangan fallback ke email, NIP, atau header browser.
- [ ] Pertahankan error contract 401/403/404/409.
- [ ] Tambahkan audit metadata aman tanpa token, secret, atau PII berlebih.
- [ ] Tambahkan OpenAPI/Flasgger docs untuk token contract.

### Test wajib Phase 2

- [ ] valid delegated token + active linked employee → 200.
- [ ] expired token → 401.
- [ ] invalid signature/kid → 401.
- [ ] issuer salah → 401.
- [ ] audience salah → 403.
- [ ] azp/client salah → 403.
- [ ] scope salah → 403.
- [ ] registration revoked → 403.
- [ ] unknown subject → 404.
- [ ] inactive employee → 403.
- [ ] duplicate/conflicting link → 409.
- [ ] service-account subject tanpa user delegation → tidak boleh menjadi profile user.
- [ ] field di luar allowlist tidak keluar.

### Gate Phase 2

```text
[ ] Contract suite lulus.
[ ] Full pytest lulus.
[ ] Registration status benar-benar diperiksa.
[ ] Profile allowlist aktif.
[ ] Tidak ada custom trusted subject header.
```

## Phase 3 — `s1-jabar` backend

- [ ] Pertahankan login OIDC, PKCE, state, nonce, callback, logout.
- [ ] Simpan user identity tervalidasi pada session server-side.
- [ ] Implementasikan `IdpPegawaiProfileClient` server-side.
- [ ] Implementasikan token exchange/delegation server-side.
- [ ] Cache delegated token sampai mendekati expiry.
- [ ] Refresh/mint ulang token tanpa interaksi browser.
- [ ] Kirim hanya token hasil exchange ke profile API.
- [ ] Kirim `X-Consumer-Code: s1-feed` sebagai metadata, bukan trust identity.
- [ ] Tambahkan timeout, retry terbatas, dan safe error mapping.
- [ ] Jangan menyimpan token di frontend/localStorage.
- [ ] Jangan memakai UserInfo sebagai source status/NIP/unit.
- [ ] Profile response disimpan seperlunya di session/cache lokal.
- [ ] User inactive tidak boleh masuk route aplikasi.

### Test wajib Phase 3

- [ ] active user login → token exchange → profile 200.
- [ ] unknown identity → safe 404/denial.
- [ ] inactive employee → safe 403/denial.
- [ ] callback state/nonce/PKCE mismatch ditolak.
- [ ] token exchange gagal ditangani aman.
- [ ] profile API timeout ditangani aman.
- [ ] service credential tidak muncul di browser/log.
- [ ] `php artisan test` lulus.
- [ ] `yarn run build` lulus.

### Gate Phase 3

```text
[ ] Browser login/callback/logout lulus.
[ ] Profile active tampil dari IDP.
[ ] Inactive ditolak.
[ ] Unknown ditolak.
[ ] Tidak ada token di browser/log.
[ ] Test Laravel dan build lulus.
```

## Phase 4 — Local rehearsal end-to-end

- [ ] Restart stack dari konfigurasi bersih yang terdokumentasi.
- [ ] Login `demo.s1`.
- [ ] Verifikasi callback dan session.
- [ ] Verifikasi token exchange secara status-only.
- [ ] Profile active → 200.
- [ ] Uji user tanpa identity link → 404.
- [ ] Uji pegawai nonaktif → 403.
- [ ] Uji logout dan session invalidation.
- [ ] Uji expired/invalid token.
- [ ] Periksa logs untuk memastikan token/cookie/secret tidak bocor.
- [ ] Catat evidence metadata aman.

## Phase 5 — Generalisasi consumer

Setelah `s1-jabar` GREEN:

- [ ] Bekukan reusable client contract.
- [ ] Buat registration terpisah untuk `s2-jabar`.
- [ ] Buat registration terpisah untuk `dasborkanwil`.
- [ ] Buat registration terpisah untuk portal Kabayan/Pasti.
- [ ] Setiap consumer memiliki client credential dan field profile sendiri.
- [ ] Jangan berbagi secret antar consumer.
- [ ] Evaluasi bootstrap/delta feed Dokumen 31 hanya bila butuh cache lokal/offline/volume besar.
- [ ] Jangan membangun feed penuh sebagai blocker pilot profile.

## Keputusan fallback jika token exchange Keycloak tidak tersedia

Fallback hanya boleh dipilih melalui perubahan kontrak eksplisit:

```text
Two-token request:
- Authorization: service JWT s1-feed
- X-User-Token: user OIDC token
```

IDP memvalidasi kedua token secara cryptographic. Tidak boleh memakai subject header mentah. Fallback harus memiliki test, docs, dan promotion gate yang sama. Jangan membuat dev-only adapter yang akan dibuang kemudian.

## Prioritas eksekusi tercepat

```text
1. Freeze token exchange claim contract.
2. Buktikan Keycloak token exchange lokal.
3. Tambah contract test IDP untuk delegated token.
4. Tambah registration-status dan profile allowlist check.
5. Implement IdpPegawaiProfileClient exchange flow di s1-jabar.
6. Jalankan active/inactive/unknown rehearsal.
7. Full test + build.
8. Baru generalisasi ke consumer lain.
```

## Definition of Done

```text
[x] IDP tetap source of truth.
[x] Human login tetap Keycloak.
[x] Service client terpisah dari human client.
[ ] Token profile user-bound melalui exchange/delegation.
[ ] Tidak ada static service JWT.
[ ] Tidak ada custom subject header.
[ ] Registration aktif diperiksa.
[ ] Profile allowlist diperiksa.
[ ] Active/unknown/inactive contract lulus.
[ ] s1-jabar end-to-end lulus.
[ ] Pattern siap dipakai consumer berikutnya.
```

## Handoff command untuk `s1-jabar`

Jalankan dari project/container `s1-jabar` setelah middleware profile dibuat;
jangan menjalankan token exchange dari callback OIDC:

```bash
php artisan test
yarn run build
```

Smoke browser wajib melaporkan metadata aman saja:

```text
login callback = pass
session = pass
profile active = HTTP 200
profile inactive = HTTP 403
unknown identity = HTTP 404
profile dependency failure = HTTP 403/503, bukan login 401
```

Tidak boleh dilaporkan: access token, refresh token, cookie, secret,
password, raw claims, atau PII.

## Hal yang sengaja tidak dikerjakan

- Production deployment.
- DNS/TLS production.
- Perubahan destructive database.
- Impersonation bebas di Keycloak.
- Shared credential lintas consumer.
- Full delta feed sebelum kebutuhan cache/offline terbukti.
