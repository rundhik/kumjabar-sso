# Pemisahan Compose Keycloak dan IDP Pegawai

## Struktur

```text
kumjabar-sso/
├── keycloak/
│   └── docker-compose.yml       # hanya service kumjabar_keycloak (env dari ../idp-pegawai/.env)
├── idp-pegawai/
│   ├── docker-compose.yml       # hanya service kumjabar_idp
│   └── .env                     # single source env lokal, tidak di-commit (tidak ada .env duplikat di root)
├── src/
├── migrations/
└── alembic.ini
```

> Catatan: `.env` duplikat di root proyek telah dihapus untuk menghindari ambiguitas.
> Satu-satunya source adalah `idp-pegawai/.env` (contoh aman di `idp-pegawai/.env.example`).

Kedua Compose memakai external Docker network `project_network`. Karena itu service dapat saling mengakses melalui nama container `kumjabar_keycloak`, sementara PostgreSQL tetap diakses melalui `global_postgresql`.

## Menjalankan

Dari project root:

```bash
# Pastikan network tersedia
# docker network create project_network  # hanya jika belum ada

# Start Keycloak; tidak tergantung pada IDP
# keycloak/docker-compose.yml sudah memakai env_file: ../idp-pegawai/.env
docker compose --env-file idp-pegawai/.env -f keycloak/docker-compose.yml up -d

# Start IDP secara terpisah (env_file: .env relatif terhadap idp-pegawai/)
cd idp-pegawai
docker compose up -d
# atau dari root:
# docker compose --env-file idp-pegawai/.env -f idp-pegawai/docker-compose.yml up -d
```

Recreate IDP saja:

```bash
cd idp-pegawai
docker compose up -d --force-recreate kumjabar_idp
```

Perintah tersebut tidak melakukan restart/recreate service Keycloak.

Stop IDP saja:

```bash
docker compose -f docker-compose.yml stop kumjabar_idp
```

Status kedua project:

```bash
docker compose --env-file idp-pegawai/.env -f keycloak/docker-compose.yml ps
docker compose -f idp-pegawai/docker-compose.yml ps
```

## Boundary

- `keycloak/docker-compose.yml` tidak memiliki `depends_on` terhadap IDP dan memakai `env_file: ../idp-pegawai/.env`.
- `idp-pegawai/docker-compose.yml` tidak memiliki service Keycloak dan tidak memakai `depends_on` lintas Compose project.
- Jangan memakai `docker compose down -v` pada environment yang memiliki database persisten.
- `quay.io/keycloak/keycloak:latest` dan `start-dev` tetap hanya untuk development; staging harus memakai image pinned dan HTTPS.
- Nilai `.env` tidak boleh dimasukkan ke commit, log, atau laporan.
