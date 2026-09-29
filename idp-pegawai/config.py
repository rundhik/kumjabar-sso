"""Environment-backed configuration for the IDP application."""

import json
import locale
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Base configuration shared by development, testing, and production."""

    TESTING = _bool("FLASK_TESTING")
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")
    APP_NAME = os.getenv("APP_NAME", "Kumjabar SSO")
    APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Jakarta")
    FLASK_DEBUG = _bool("FLASK_DEBUG")
    CORS_ALLOWED_ORIGINS = [x.strip() for x in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")]

    SQLALCHEMY_TRACK_MODIFICATIONS = _bool("SQLALCHEMY_TRACK_MODIFICATIONS")
    SQLALCHEMY_ECHO = _bool("SQLALCHEMY_ECHO")
    SQLALCHEMY_RECORD_QUERIES = _bool("SQLALCHEMY_RECORD_QUERIES")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///:memory:")
    TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
    CELERY_TASK_IGNORE_RESULT = _bool("CELERY_TASK_IGNORE_RESULT", True)
    SESSION_TYPE = "redis"
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.getenv("SESSION_LIFETIME_HOURS", "12")))

    KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://kumjabar_keycloak:8080").rstrip("/")
    KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "")
    KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "")
    KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "")
    KEYCLOAK_ALLOW_INSECURE_DEV = False
    INTERNAL_PROFILE_ISSUER = os.getenv("INTERNAL_PROFILE_ISSUER", "")
    INTERNAL_PROFILE_AUDIENCE = os.getenv("INTERNAL_PROFILE_AUDIENCE", "idp-pegawai-internal")
    INTERNAL_PROFILE_CLIENT = os.getenv("INTERNAL_PROFILE_CLIENT", "s1-jabar-token-exchange")
    # Optional non-secret catalog for approved consumer authorization. An empty
    # catalog preserves injected contract-test authorizers; configured runtime
    # environments fail closed on unknown consumers.
    # INTERNAL_PROFILE_REGISTRATIONS = json.loads(os.getenv("INTERNAL_PROFILE_REGISTRATIONS", "{}"))
    INTERNAL_PROFILE_REGISTRATIONS = {
        "s1-jabar-token-exchange": {
            "status": "active",
            "allowed_resource_families": ["pegawai-profile"],
            "allowed_field_profile": "pegawai-profile.v1"
        }
    }
    _INTERNAL_PROFILE_JWKS_RAW = json.loads(os.getenv("INTERNAL_PROFILE_JWKS", "{}"))
    # Accept Keycloak's standard {"keys": [...]} document and normalize it to
    # the kid -> JWK mapping consumed by the fail-closed validator.
    INTERNAL_PROFILE_JWKS = {
        str(key["kid"]): key
        for key in _INTERNAL_PROFILE_JWKS_RAW.get("keys", [])
        if isinstance(key, dict) and key.get("kid")
    } if isinstance(_INTERNAL_PROFILE_JWKS_RAW, dict) and isinstance(_INTERNAL_PROFILE_JWKS_RAW.get("keys"), list) else _INTERNAL_PROFILE_JWKS_RAW

    SWAGGER = {
        "title": os.getenv("SWAGGER_TITLE", "Kumjabar SSO API"),
        "uiversion": 3,
        "openapi": "3.0.2",
    }
    FORMIO_DEFAULT_BUILDER_OPTIONS = json.loads(os.getenv("FORMIO_DEFAULT_BUILDER_OPTIONS", "{}"))

    DB_DRIVER = os.getenv("DB_DRIVER", "postgresql").lower().replace("pgsql", "postgresql")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST = os.getenv("DB_HOST", "global_postgresql")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "db_sso")

    @staticmethod
    def build_db_uri(driver, user, password, host, port, name):
        if driver == "mysql":
            return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"
        if driver == "oracle":
            return f"oracle://{user}:{password}@{host}:{port}/{name}"
        if driver == "sqlite":
            return f"sqlite:///{BASE_DIR}/app.db"
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"

    @classmethod
    def init_app(cls, app):
        try:
            locale.setlocale(locale.LC_TIME, "id_ID.utf8" if os.name != "nt" else "id_ID")
        except locale.Error:
            pass


class Production(Config):
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", Config.build_db_uri(Config.DB_DRIVER, Config.DB_USER, Config.DB_PASSWORD, Config.DB_HOST, Config.DB_PORT, Config.DB_NAME)
    )


class Development(Production):
    DEVELOPMENT = True
    # Local-only development wiring; Production remains deny-by-default.
    IMPORT_STORAGE_DIR = os.getenv("IMPORT_STORAGE_DIR", "/var/lib/kumjabar/imports")
    IMPORT_ORG_CODES = tuple(code.strip() for code in os.getenv("IMPORT_ORG_CODES", "").split(",") if code.strip())
    from .access.catalog import Capability, Role, ScopeType
    from .access.grants import AccessGrant
    # Local development console explicitly enables the admin CRUD role.
    # Production remains deny-by-default because it does not inherit this class.
    UI_GRANTS = (
        AccessGrant(Role.ACCESS_ADMIN, ScopeType.GLOBAL),
        AccessGrant(Role.IMPORT_OPERATOR, ScopeType.GLOBAL),
        AccessGrant(Role.IMPORT_APPROVER, ScopeType.GLOBAL),
    )
    ADMIN_GRANTS = (AccessGrant(Role.ACCESS_ADMIN, ScopeType.GLOBAL),)
    IMPORT_GRANTS = tuple(Capability)
    FLASK_DEBUG = _bool("FLASK_DEBUG", True)
    KEYCLOAK_ALLOW_INSECURE_DEV = _bool("KEYCLOAK_ALLOW_INSECURE_DEV", False)


class Testing(Config):
    TESTING = True
    LOGIN_DISABLED = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")


config_dict = {"production": Production, "development": Development, "testing": Testing, "default": Production}

# Compatibility aliases used by older callers.
ConfigClass = Config

__all__ = ["Config", "Production", "Development", "Testing", "config_dict"]
