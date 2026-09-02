# Runbook Readiness Sprint 4–5 (non-production)

## Tujuan dan batasan
Artefak ini untuk rehearsal lokal/staging-like saja. Tidak menjalankan Keycloak production,
DNS/TLS production, atau perubahan database destruktif. Semua evidence dari unit/contract test
bersifat **synthetic** dan tidak membuktikan konektivitas eksternal.

## Gate sebelum staging
1. Audit statis compose: image Keycloak harus exact-pinned, command bukan `start-dev`, dan
   HTTP plaintext tidak aktif.
2. Audit gateway: route `/internal/`, `/feed/`, dan `/worker/` tidak boleh berada di public
   allow-list; private ingress wajib service JWT, audience dan scope; upstream TLS verification on.
3. Audit OIDC: discovery/JWKS, PKCE S256, state, nonce, issuer, audience/azp, dan key rotation.
4. Jalankan targeted suite:
   `PYTHONPATH=idp-pegawai pytest -q tests/unit/test_phase57_readiness.py tests/contract/test_phase56_gateway_contract.py tests/unit/integrations tests/unit/test_consumer_feed.py`

## Rehearsal consumer
- Bootstrap: capture cutoff sekali, page sampai selesai, apply tiap page, commit opaque checkpoint,
  lalu lanjut delta. Row setelah cutoff masuk delta, bukan bootstrap.
- Replay: gunakan cursor bertanda consumer registration/resource family/profile/version; cursor
  invalid/expired harus ditolak dan consumer melakukan bootstrap ulang sesuai kebijakan.
- Conflict: kirim event yang sama dua kali; payload hash dan change sequence harus idempotent.
  Versi lebih lama tidak boleh menimpa snapshot versi lebih baru.
- Lifecycle: suspend registration menolak feed; reactivation hanya setelah scope/audience dan
  checkpoint tervalidasi. Jangan menghapus data produksi saat rehearsal.

## Gateway deny rehearsal
Uji request anonymous dan JWT tanpa scope ke private paths; ekspektasi 404/401 sesuai adapter,
dan pastikan request tidak diteruskan ke upstream. Uji JWT service valid hanya pada private
network dengan audience `idp-pegawai-internal` dan scope `feed:read`.

## Evidence classification
- **Synthetic**: pytest fixtures, static YAML review, dry-run lokal.
- **External/runtime**: HTTPS endpoint, discovery/JWKS fetch, proxy certificate verification,
  real consumer registration/change-log, dan PostgreSQL-in-Docker. Gate staging tetap BLOCKED
  sampai evidence external tersebut dikumpulkan secara terpisah.

## Rollback projection
Hentikan worker projection, simpan reconciliation report dan identity-link diff, rollback hanya
ke desired state terakhir yang disetujui, lalu replay outbox dari checkpoint. Jangan mengedit
Keycloak manual sebagai pengganti source-of-truth IDP.

## Insiden
Redact token, cookie, cursor, payload, dan PII dari log. Nonaktifkan consumer registration
terdampak, rotasi credential staging, dan buka kembali setelah readiness checks GREEN.

## Exit criteria
Targeted suite GREEN, semua static blockers resolved, rehearsal lifecycle/replay/conflict
tercatat, serta evidence runtime eksternal dilampirkan. Tanpa itu status hanya `synthetic-ready`.
