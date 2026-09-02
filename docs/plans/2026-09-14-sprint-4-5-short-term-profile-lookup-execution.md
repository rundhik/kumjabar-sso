# Execution Plan — Sprint 4–5 Short-Term Profile Lookup

Tanggal: 2026-09-14  
Kontrak utama: `docs/architecture/36-idp-pegawai-consumer-profile-lookup-s1-client-contract.md`  
Pilot: `s1-jabar`  
Status awal: **READY TO IMPLEMENT LOCALLY**

## Tujuan

Membuktikan jalur end-to-end berikut tanpa menunggu VPS/domain/TLS staging:

```text
s1-jabar login ke Keycloak
        ↓
session Laravel terbentuk
        ↓
backend s1-jabar meminta profil ke IDP Pegawai
        ↓
IDP resolve provider + issuer + subject
        ↓
s1-jabar menerima profil pegawai curated
        ↓
pegawai aktif boleh masuk, pegawai nonaktif ditolak
```

## Batas scope

### Dikerjakan sekarang

- profile lookup satu caller/pegawai;
- route private versioned;
- service JWT validation atau adapter synthetic lokal yang eksplisit;
- identity-link resolution;
- response `pegawai-profile.v1`;
- active/inactive/unknown/error behavior;
- Flasgger docs;
- contract tests;
- wiring backend `s1-jabar`;
- local HTTP development.

### Tidak dikerjakan sekarang

- VPS/domain Pusdatin;
- TLS staging/production;
- gateway production;
- consumer bootstrap/delta penuh;
- multi-client rollout;
- perubahan database production;
- pemindahan RBAC/ABAC client ke Keycloak.

## Checklist Phase A — Bekukan kontrak

- [x] Dokumen arsitektur nomor 36 dibuat.
- [x] Route canonical: `/idp-pegawai/internal/api/v1/consumer/profile`.
- [x] Contract version: `pegawai-profile.v1`.
- [x] Error codes 401/403/404/409 ditetapkan.
- [x] Field profile allowlist ditetapkan.
- [x] Boundary Keycloak/IDP/client ditetapkan.

## Checklist Phase B — IDP Pegawai

- [x] Implementasi repository lookup provider/issuer/subject.
- [x] Implementasi service profile resolution.
- [x] Implementasi auth guard service JWT dengan JWKS/configuration fail-closed.
- [x] Implementasi local synthetic adapter untuk development/test jika diperlukan.
- [x] Implementasi route canonical.
- [x] Tambahkan Flasgger docs.
- [x] Serialize hanya field profile yang diizinkan.
- [x] Pastikan inactive/unknown error sesuai kontrak.
- [x] Tambahkan test valid token + linked active pegawai.
- [x] Tambahkan test invalid token.
- [x] Tambahkan test audience/azp/scope/registration.
- [x] Tambahkan test unknown identity.
- [x] Tambahkan test inactive employee.
- [ ] Tambahkan test conflict end-to-end setelah fixture multi-link tersedia.
- [x] Tambahkan privacy/secret leakage test.

## Checklist Phase C — `s1-jabar`

- [ ] Pertahankan login/callback/logout yang sudah lulus.
- [ ] Jangan memakai UserInfo sebagai source status/NIP/unit.
- [ ] Tambahkan `IdpPegawaiProfileClient` server-side.
- [ ] Tambahkan timeout dan safe error mapping.
- [ ] Simpan identity link lokal sesuai keputusan project.
- [ ] Buat/update local User tanpa menjadikan email sebagai identity utama.
- [ ] Tolak session aplikasi untuk response `pegawai_inactive`.
- [ ] Tambahkan profile page/protected route.
- [ ] Tambahkan feature tests lookup sukses/gagal.
- [ ] Jalankan `php artisan test` melalui container PHP.
- [ ] Jalankan `yarn run build`.

## Checklist Phase D — Local rehearsal

- [ ] Keycloak lokal aktif pada `http://localhost:8080`.
- [ ] IDP lokal aktif pada `http://localhost:9999`.
- [ ] `s1-jabar` lokal aktif pada port development.
- [ ] Login browser berhasil.
- [ ] Callback berhasil.
- [ ] Profile request backend berhasil.
- [ ] Profil nama/NIP/unit/status tampil sesuai profile.
- [ ] Pegawai nonaktif ditolak.
- [ ] Identity tidak dikenal ditolak.
- [ ] Logout berhasil.
- [ ] Tidak ada token di localStorage.
- [ ] Tidak ada token/secret/cookie/raw PII di log.

## Acceptance criteria end-to-end

Capaian short-term dianggap GREEN jika terlihat:

```text
[ ] Login → Keycloak → callback → Laravel session
[ ] Laravel backend → official IDP profile API
[ ] Response contract_version = pegawai-profile.v1
[ ] Profil berasal dari IDP, bukan UserInfo untuk status/unit
[ ] Active employee diterima
[ ] Inactive employee ditolak
[ ] Unknown identity ditolak
[ ] Logout menghapus session
[ ] Negative security tests lulus
[ ] Test dan frontend build lulus
```

## Evidence handoff ke `kumjabar-sso`

Laporkan hanya metadata aman:

- route dan method;
- contract version;
- status test dan jumlah pass;
- status login/callback/logout;
- status active/inactive/unknown;
- status PKCE/state/nonce/issuer/audience/azp;
- screenshot tanpa token/cookie/PII tidak perlu;
- blocker teknis.

Jangan kirim access token, refresh token, cookie, client secret, password, isi `.env`, atau workbook/data pegawai nyata.

## Gate menuju consumer feed

Jangan membangun bootstrap/delta penuh sebelum profile lookup GREEN. Setelah GREEN, evaluasi kebutuhan feed berdasarkan:

- jumlah record/client;
- kebutuhan cache lokal;
- freshness;
- toleransi IDP unavailable;
- kebutuhan offline;
- beban request login.

Jika belum dibutuhkan, profile lookup tetap menjadi solusi yang sah untuk pilot.

## Status dan langkah sesi berikutnya

Status saat dokumen dibuat:

```text
Architecture contract: FROZEN
IDP implementation: PENDING
s1-jabar wiring: PENDING
Local rehearsal: PENDING
Staging/external: BLOCKED BY HOSTNAME/TLS AVAILABILITY
```

Prompt sesi berikutnya di project ini:

```text
Baca dokumen arsitektur 36 dan execution plan 2026-09-14.
Implementasikan Phase B IDP Pegawai saja: repository/service lookup
provider+issuer+subject dan endpoint profile canonical. Jangan mengubah
production atau memakai endpoint admin. Tambahkan Flasgger dan tests.
```

Prompt setelah Phase B GREEN di project `s1-jabar`:

```text
Baca AGENTS.md dan kontrak profile dari kumjabar-sso. Ganti lookup
status/NIP/unit dari Keycloak UserInfo menjadi IdpPegawaiProfileClient
server-side. Pertahankan login OIDC, PKCE, state, nonce, dan logout.
Tambahkan tests serta jalankan build.
```

## Gate produksi

Production tetap BLOCKED sampai staging memiliki hostname, HTTPS/TLS, trusted proxy, service JWT nyata, private route, discovery/JWKS runtime, dan evidence operasional.

## Catatan

Dokumen ini sengaja memisahkan target cepat yang dapat dikerjakan lokal dari hardening staging/production yang menunggu Pusdatin.
