# Pemisahan Compose Keycloak dan IDP Pegawai

## Struktur

```text
kumjabar-sso/
├── keycloak/
│   └── docker-compose.yml       # hanya service kumjabar_keycloak
├── idp-pegawai/
│   └── docker-compose.yml       # hanya service kumjabar_idp
├── src/
├── migrations/
├── alembic.ini
└── .env                         # shared local env, tidak di-commit
```

Kedua Compose memakai external Docker network `project_network`. Karena itu service dapat saling mengakses melalui nama container `kumjabar_keycloak`, sementara PostgreSQL tetap diakses melalui `global_postgresql`.

## Menjalankan

Dari project root:

```bash
# Pastikan network tersedia
# docker network create project_network  # hanya jika belum ada

# Start Keycloak; tidak tergantung pada IDP
cd keycloak
docker compose --env-file ../.env -f docker-compose.yml up -d

# Start IDP secara terpisah
cd ../idp-pegawai
docker compose --env-file ../.env -f docker-compose.yml up -d
```

Recreate IDP saja:

```bash
cd idp-pegawai
docker compose --env-file ../.env -f docker-compose.yml up -d --force-recreate kumjabar_idp
```

Perintah tersebut tidak melakukan restart/recreate service Keycloak.

Stop IDP saja:

```bash
docker compose --env-file ../.env -f docker-compose.yml stop kumjabar_idp
```

Status kedua project:

```bash
docker compose --env-file ../.env -f keycloak/docker-compose.yml ps
docker compose --env-file ../.env -f idp-pegawai/docker-compose.yml ps
```

## Boundary

- `keycloak/docker-compose.yml` tidak memiliki `depends_on` terhadap IDP.
- `idp-pegawai/docker-compose.yml` tidak memiliki service Keycloak dan tidak memakai `depends_on` lintas Compose project.
- Jangan memakai `docker compose down -v` pada environment yang memiliki database persisten.
- `quay.io/keycloak/keycloak:latest` dan `start-dev` tetap hanya untuk development; staging harus memakai image pinned dan HTTPS.
- Nilai `.env` tidak boleh dimasukkan ke commit, log, atau laporan.
