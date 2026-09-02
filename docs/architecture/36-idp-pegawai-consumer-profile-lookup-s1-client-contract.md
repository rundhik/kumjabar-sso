# 36 - Kontrak Consumer Profile Lookup untuk Client `s1-jabar`

Status: **APPROVED FOR SHORT-TERM DEVELOPMENT**

### User-bound contract freeze (2026-09-17)

The pilot uses a **user-bound delegated access token** as the production-shaped
mechanism. Standard Token Exchange V2 is the preferred issuer mechanism when
the backend requester is configured as an authenticated confidential client.
The public browser login client is not itself a service identity and must not
be given a client secret merely to force token exchange.

The two identities remain separate:

```text
human identity = provider=keycloak + exact issuer + token sub
application identity = approved consumer registration/client binding
```

The IDP resolves an employee only from `provider + issuer + provider_subject`.
Email, username, NIP, browser headers, and the `s1-feed` service-account
subject are never identity substitutes. Until a backend requester and its
final `azp` binding are proven, `IDP_PEGAWAI_AUTHORIZATION_ENABLED` remains
false and `s1-jabar` must not call this flow from its OIDC callback.  
Proyek: `kumjabar-sso`  
Tanggal: 2026-09-14  
Melanjutkan: Dokumen 30–35  
Pilot client: `s1-jabar`

## 1. Tujuan

Dokumen ini membekukan kebutuhan jangka pendek agar aplikasi client dapat:

```text
user login di Keycloak
        ↓
s1-jabar membuat session Laravel
        ↓
s1-jabar backend meminta profil resmi ke IDP Pegawai
        ↓
IDP mengembalikan status dan afiliasi pegawai
```

Target ini sengaja lebih kecil daripada consumer bootstrap/delta penuh. Tujuannya adalah membuktikan jalur SSO end-to-end pada satu client tanpa membuat sistem sinkronisasi lokal sebelum diperlukan.

## 2. Keputusan Arsitektur

### 2.1 Login manusia dan data pegawai dipisahkan

- Keycloak adalah authority untuk autentikasi dan token OIDC manusia.
- IDP Pegawai adalah authority untuk identitas ASN, eligibility/status, identity link, dan afiliasi organisasi.
- `s1-jabar` tidak memakai Keycloak UserInfo sebagai sumber kebenaran `status_pegawai`, `is_active`, NIP, atau unit organisasi.
- `s1-jabar` tidak mengakses PostgreSQL IDP secara langsung.
- `s1-jabar` tidak memakai endpoint admin sebagai API profil client.

### 2.2 API jangka pendek

API canonical untuk pilot adalah:

```http
GET /idp-pegawai/internal/api/v1/consumer/profile
```

Nama resource boleh diwujudkan oleh implementasi sebagai route blueprint yang setara, tetapi public contract final harus menggunakan prefix dan versioning di atas. Route internal hanya boleh tersedia melalui private service path; localhost development boleh memakai HTTP.

Request tidak memiliki body. Caller dikaitkan dengan identity user-bound yang telah divalidasi secara kriptografis. Jalur utama production adalah delegated/token-exchange JWT: service authorization untuk consumer dan subject user berada pada token yang dipercaya IDP. Client-credentials token murni yang hanya membawa subject service account tidak boleh dipakai untuk mengidentifikasi pegawai. Custom header subject mentah dan adapter synthetic bukan bagian dari kontrak production.

## 3. Service Authentication

Request production/staging menggunakan user-bound delegated JWT hasil token exchange/delegation. Client-credentials service JWT murni hanya dapat membuktikan consumer dan tidak cukup untuk lookup pegawai user.

Token profile wajib memuat:

```text
iss, sub, aud, azp, exp, iat
scope = profile:read
sub = subject user yang telah diautentikasi
azp/client binding = consumer yang diizinkan
```

Request production/staging menggunakan service-to-service JWT:

```text
consumer registration: s1-feed
resource: pegawai profile
required scope: profile:read
expected audience: idp-pegawai-internal
```

IDP wajib memvalidasi:

- signature melalui JWKS yang dipercaya;
- `iss` exact;
- `aud` exact;
- `azp` sesuai registration;
- `exp`/waktu token;
- scope `profile:read`;
- status consumer registration;
- allowed resource/field profile.

`X-Consumer-Code` boleh dipakai sebagai metadata lookup setelah token valid, tetapi **bukan pengganti JWT validation**.

Untuk development lokal, adapter synthetic boleh digunakan hanya pada test/local configuration. Adapter tersebut harus fail closed di staging/production.

## 4. Identity Resolution

Identity caller atau subject pegawai harus diselesaikan melalui:

```text
provider + issuer + provider_subject
        ↓
pegawai_identity_links
        ↓
pegawai
        ↓
eligibility/status check
```

Email hanya boleh menjadi atribut lookup/linking yang terkontrol, bukan identifier utama setelah identity link tersedia. NIP tidak dikirim dari browser sebagai kunci trust.

Jika identity link conflict atau provider subject terhubung ke lebih dari satu pegawai, request ditolak dan diaudit tanpa memilih otomatis.

## 5. Response Contract `pegawai-profile.v1`

Response sukses minimal:

```json
{
  "data": {
    "pegawai_uuid": "uuid-sintetis",
    "nama_lengkap": "Nama Pegawai",
    "status_pegawai": "aktif",
    "is_active": true,
    "primary_org_unit": {
      "uuid": "uuid-unit",
      "code": "TUM_TI",
      "name": "Unit Teknologi Informasi"
    }
  },
  "meta": {
    "source": "idp-pegawai",
    "contract_version": "pegawai-profile.v1"
  }
}
```

Field restricted seperti NIP dan email hanya dikeluarkan jika field profile `s1-feed` secara eksplisit mengizinkannya. Default profile tidak boleh mengirim token, password, raw claims, storage key, audit payload, atau data pegawai lain.

## 6. Error Contract

| Kondisi | HTTP | Code |
|---|---:|---|
| token tidak ada/tidak valid/expired | 401 | `service_token_invalid` |
| audience/azp/scope/registration tidak sesuai | 403 | `consumer_not_allowed` |
| identity link tidak ditemukan | 404 | `pegawai_identity_not_found` |
| pegawai ditemukan tetapi tidak eligible/aktif | 403 | `pegawai_inactive` |
| identity link conflict | 409 | `identity_link_conflict` |
| resource/profile tidak diizinkan | 403 | `profile_not_allowed` |

Pesan response aman dan tidak mengungkap detail internal database, token, atau identity link lain.

## 7. Batasan Route

Endpoint ini bukan pengganti:

```text
/admin/*                         = human admin UI/API
/internal/feed/*                 = feed bootstrap/delta jangka menengah
/idp-pegawai/internal/api/v1/... = canonical private consumer family
```

Dokumen 31 tetap menjadi arah untuk feed cursor/replay/checkpoint. Profile lookup adalah vertical slice pendek untuk membuktikan konsumsi client sebelum sinkronisasi snapshot lokal dibangun.

## 8. Flow Client `s1-jabar`

```text
Browser -> Keycloak Authorization Code + PKCE S256
Keycloak -> s1-jabar callback
s1-jabar -> validasi issuer/audience/azp/state/nonce
s1-jabar backend -> service token / private profile API
IDP -> resolve provider+issuer+subject
IDP -> curated pegawai-profile.v1
s1-jabar -> local Laravel session
```

Service token tidak boleh berada di browser atau `localStorage`. Browser hanya menerima session application yang dilindungi cookie Laravel.

## 9. Local Development vs Staging

Development saat ini boleh memakai:

```text
Keycloak  http://localhost:8080
IDP       http://localhost:9999
s1-jabar http://localhost:8000
```

TLS/domain/VPS bukan prerequisite untuk pilot localhost. Staging wajib menambahkan HTTPS, hostname strict, trusted proxy, private route, JWKS, dan service JWT nyata sebelum digunakan di luar host development.

## 10. Acceptance Criteria

### IDP Pegawai

- [ ] Route canonical dan Flasgger documentation tersedia.
- [ ] Lookup provider/issuer/subject tersedia.
- [ ] Service JWT validation tersedia dan fail closed.
- [ ] Registration, audience, azp, dan scope diperiksa.
- [ ] Response memakai `pegawai-profile.v1`.
- [ ] Field profile allowlist diterapkan.
- [ ] User inactive menghasilkan `403 pegawai_inactive`.
- [ ] Unknown identity menghasilkan `404 pegawai_identity_not_found`.
- [ ] Conflict menghasilkan `409 identity_link_conflict`.
- [ ] Tidak ada direct database access dari client.

### `s1-jabar`

- [ ] Login/callback/logout yang sudah ada tetap lulus.
- [ ] UserInfo Keycloak tidak lagi menjadi sumber status/NIP/unit.
- [ ] Backend memanggil profile API resmi.
- [ ] Profil pegawai tampil dari response IDP.
- [ ] User inactive ditolak.
- [ ] Service credential tidak muncul di browser/log.
- [ ] Test positive dan negative tersedia.

## 11. Promotion Gate

Status implementasi boleh naik dari `synthetic-ready` ke `staging-ready` hanya jika:

1. contract test IDP dan client lulus;
2. route private tidak public;
3. service JWT validation lulus negative tests;
4. profile allowlist lulus privacy check;
5. browser login/callback/logout lulus;
6. active dan inactive employee rehearsal tercatat;
7. tidak ada token, cookie, secret, atau PII berlebih di log/evidence.

Dokumen ini tidak mengizinkan perubahan production, DNS, TLS production, atau database destruktif.

## 12. Hubungan dengan Tahap Berikutnya

Setelah profile lookup stabil, pilih salah satu berdasarkan kebutuhan:

- tetap profile lookup saat login jika jumlah client kecil dan freshness cukup;
- lanjut consumer bootstrap/delta Dokumen 31 jika client membutuhkan cache lokal, volume besar, offline tolerance, atau multi-application distribution.

Keputusan itu harus didasarkan pada evidence penggunaan, bukan asumsi bahwa semua client wajib memiliki replika penuh.

## 13. Ringkasan Keputusan

```text
s1-jabar login       = Keycloak OIDC human flow
profil/status ASN    = IDP Pegawai profile API
permission fitur S1  = s1-jabar
TLS                  = belum wajib untuk localhost development
feed snapshot/delta  = tahap berikutnya, bukan blocker pilot pertama
```

Status akhir kontrak: **dibekukan untuk implementasi short-term lokal**.
