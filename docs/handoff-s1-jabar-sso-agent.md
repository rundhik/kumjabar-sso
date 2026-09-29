# Memorandum Handoff — SSO `s1-jabar` melalui Keycloak + IDP Pegawai

Tanggal: 2026-09-17
Sumber: `/home/user/projects/kumjabar-sso`
Status: **IDP-side preflight GREEN; pindah ke project `s1-jabar` belum diizinkan untuk implementasi sebelum user-bound token evidence tersedia**

## Tujuan

Membuat flow berikut:

```text
Browser s1-jabar
  -> Keycloak Authorization Code + PKCE
  -> callback s1-jabar
  -> session server-side
  -> backend s1-jabar melakukan token exchange/delegation
  -> token user-bound dikirim ke IDP Pegawai
  -> GET /idp-pegawai/internal/api/v1/consumer/profile
  -> pegawai-profile.v1 atau denial
```

## Authority boundary

- Keycloak: autentikasi manusia dan penerbit token.
- IDP PostgreSQL: source of truth pegawai, status, eligibility, organisasi, identity link.
- `s1-jabar`: session, authorization fitur aplikasi, dan konsumsi profile resmi.
- Client tidak boleh direct access PostgreSQL IDP.
- `s1-feed` service account tidak boleh dipakai sebagai subject pegawai.
- Dilarang mempercayai `X-User-Subject` mentah.
- Jangan menyimpan token di browser, localStorage, URL, log, atau artifact.

## Runtime evidence kumjabar-sso

- `kumjabar_keycloak`: hidup, image `quay.io/keycloak/keycloak:26.7.3`.
- `kumjabar_idp`: hidup di port `9999`.
- `s1_app`: hidup.
- `s1_nginx`: hidup di port `8000`.
- Keycloak issuer lokal: `http://localhost:8080/realms/kumjabar`.
- Discovery endpoint: HTTP 200.
- JWKS endpoint: tersedia, dua key terdeteksi secara count-only.
- Keycloak feature flag: `token-exchange-standard:v2` aktif pada compose lokal.
- Client `s1-jabar`: enabled, public OIDC client, standard flow aktif, redirect URI lokal `/auth/callback`.
- Client `s1-feed`: enabled, confidential/service-account enabled.
- IDP runtime memiliki issuer, audience, client binding, dan JWKS terkonfigurasi secara non-empty.
- Request profile tanpa Authorization ditolak HTTP 401 `service_token_invalid`.

## IDP contract

Endpoint:

```http
GET /idp-pegawai/internal/api/v1/consumer/profile
Authorization: Bearer <user-bound-delegated-token>
```

Expected token contract:

```text
iss = exact Keycloak issuer
sub = authenticated human Keycloak subject
 aud = idp-pegawai-internal
azp = approved backend consumer binding
scope includes profile:read
exp/iat valid
RS256 + known kid + trusted JWKS
```

Identity resolution hanya:

```text
provider=keycloak + iss + sub
  -> pegawai_identity_links
  -> pegawai
  -> eligibility
```

Expected results:

```text
active linked user -> 200 pegawai-profile.v1
unknown identity  -> 404 pegawai_identity_not_found
inactive employee -> 403 pegawai_inactive
invalid JWT       -> 401 service_token_invalid
wrong aud/azp/scope/registration -> 403 consumer_not_allowed
```

## Test evidence

Canonical Docker command:

```bash
docker exec kumjabar_idp sh -lc \
  'cd /usr/src/app && PYTHONPATH=/usr/src/app/idp-pegawai \
   pytest -q tests/contract/test_profile_http.py \
   tests/contract/test_user_bound_profile_contract.py \
   tests/unit/oidc/test_validator.py'
```

Observed:

```text
25 passed, 1 warning
```

Host test collection is not valid evidence currently because host Python lacks `openpyxl`; use the Docker command above.

## Important known gaps

1. Keycloak realm/client/scope/audience/token-exchange permissions are not reproducibly provisioned in repository files.
2. `--features=token-exchange-standard:v2` alone is not proof that exchange permission works.
3. No user-bound token exchange success evidence exists yet.
4. No active employee identity-link/user-demo mapping has been confirmed in this handoff.
5. Existing profile contract tests mostly inject synthetic claims; they do not all exercise app factory + real signed JWT end-to-end.
6. Runtime registration is currently config-backed; database-backed registration enforcement remains a follow-up gap before staging promotion.

## Instructions for `s1-jabar` agent

Do not modify OIDC callback to call profile API directly.

Implement in this order:

1. Preserve existing Authorization Code + PKCE, state, nonce, callback, logout.
2. Establish server-side session after valid callback.
3. Add a separate post-login/profile authorization middleware or gate.
4. Implement `IdpPegawaiProfileClient` server-side.
5. Perform token exchange/delegation only from backend.
6. Send only the resulting user-bound token to the IDP profile endpoint.
7. Never send a raw subject header and never use `s1-feed` subject as employee identity.
8. Do not place any token/client secret in frontend, URL, localStorage, logs, or session fields that are rendered to browser.
9. Map profile outcomes separately from login:
   - active profile 200: allow domain route;
   - unknown 404: deny with safe “akun belum tertaut” state;
   - inactive 403: deny with safe “pegawai tidak aktif” state;
   - IDP timeout/5xx: safe dependency-unavailable state, not “login failed” 401.
10. Add real signed-token/client integration tests where possible, plus browser smoke.

Required client-side acceptance evidence:

```text
login callback = pass
server session = pass
profile active = HTTP 200
profile inactive = HTTP 403
unknown identity = HTTP 404
logout/session invalidation = pass
token absent from browser/log = pass
php artisan test = pass
yarn run build = pass
```

## Handoff gate

It is **not yet time to claim end-to-end SSO GREEN**. Before switching implementation focus to the `s1-jabar` project, `kumjabar-sso` still needs a local user-bound token exchange evidence run using a real demo user and a confirmed IDP identity link. No secret/token should be sent to chat; only status-only/redacted metadata may be reported.

When that evidence exists, the next agent may use this memorandum as the contract and implement only the S1 backend client/middleware.

## Prohibited changes

- No production Keycloak changes.
- No production gateway/DNS/TLS changes.
- No destructive database reset.
- No shared credential between `s1-jabar`, `s1-feed`, and projection worker.
- No static JWT workaround.
- No custom trusted subject header.
- No full consumer delta feed as a blocker for this pilot.

## Current user action required

Provide/confirm, through a safe local mechanism only:

- whether a local Keycloak demo user exists;
- whether that demo user already has an exact `provider=keycloak + issuer + subject` identity link in IDP;
- if not, create the local synthetic fixture/link without sending credentials or tokens to chat.

Once confirmed, run the token-exchange status-only rehearsal before editing the sibling `s1-jabar` project.

---

## Agent response memo

The IDP-side profile contract and Docker tests are ready for the S1 integration slice. The S1 agent must not reinterpret `s1-feed` as the logged-in user. The S1 agent must preserve OIDC login and add profile authorization after callback, using backend-only user-bound delegation/token exchange.

Do not report “SSO complete” until the active/unknown/inactive profile matrix and browser callback/session/logout smoke have fresh evidence.
