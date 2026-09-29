import os

from flask import Flask

from .config import Config, config_dict
from .extensions import db
from .security import init_security


def create_app(config_object=None):
    app = Flask(__name__)
    if config_object is None:
        # FLASK_CONFIG is selected by the deployment environment. Default stays
        # production-safe; development-only UI grants are never implicit.
        config_name = os.getenv("FLASK_CONFIG", "default").lower()
        app.config.from_object(config_dict.get(config_name, Config))
    elif isinstance(config_object, dict):
        app.config.from_object(Config)
        app.config.from_mapping(config_object)
    else:
        app.config.from_object(Config)
        app.config.from_object(config_object)
    db.init_app(app)
    init_security(app)
    # Runtime repositories are wired here so server-rendered UI pages read the
    # authoritative PostgreSQL data instead of silently falling back to an
    # empty list when no test repository is injected.
    if app.config.get("ORG_UNIT_REPOSITORY") is None:
        from .repositories.org_unit_repository import OrgUnitRepository
        app.config["ORG_UNIT_REPOSITORY"] = OrgUnitRepository(db.session)
    if app.config.get("PEGAWAI_REPOSITORY") is None:
        from .repositories.pegawai_repository import PegawaiRepository
        app.config["PEGAWAI_REPOSITORY"] = PegawaiRepository(db.session)
    if app.config.get("KEYCLOAK_REALM") and app.config.get("KEYCLOAK_CLIENT_ID") and app.config.get("KEYCLOAK_CLIENT_SECRET"):
        from urllib.parse import urlsplit
        from .integrations.keycloak.policy import KeycloakEndpointPolicy
        from .integrations.keycloak.transport import KeycloakHTTPTransport
        insecure_dev = bool(app.config.get("KEYCLOAK_ALLOW_INSECURE_DEV"))
        if urlsplit(app.config["KEYCLOAK_URL"]).scheme == "https" or insecure_dev:
            policy = KeycloakEndpointPolicy(app.config["KEYCLOAK_URL"], app.config["KEYCLOAK_REALM"], app.config["KEYCLOAK_CLIENT_ID"], allow_insecure_dev=insecure_dev)
            app.extensions["keycloak_transport"] = KeycloakHTTPTransport(policy, client_id=app.config["KEYCLOAK_CLIENT_ID"], client_secret=app.config["KEYCLOAK_CLIENT_SECRET"])
    from .api import admin_bp, internal_feed_bp, import_bp, profile_bp
    from .integrations.oidc.validator import OIDCValidationError, validate_token
    from .ui import ui_bp

    def profile_authorizer(authorization, headers):
        if not authorization or not authorization.startswith("Bearer "):
            return None
        issuer = app.config.get("INTERNAL_PROFILE_ISSUER")
        jwks = app.config.get("INTERNAL_PROFILE_JWKS") or {}
        if not issuer or not jwks:
            return None
        try:
            return validate_token(
                authorization[7:].strip(), issuer=issuer,
                audience=app.config["INTERNAL_PROFILE_AUDIENCE"],
                azp=app.config["INTERNAL_PROFILE_CLIENT"], jwks=jwks,
                require_nbf=False,
            )
        except OIDCValidationError as exc:
            app.logger.warning("profile service JWT rejected: %s", str(exc))
            return None

    if app.config.get("INTERNAL_PROFILE_AUTHORIZER") is None:
        app.config["INTERNAL_PROFILE_AUTHORIZER"] = profile_authorizer

    app.register_blueprint(admin_bp)
    app.register_blueprint(internal_feed_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(ui_bp)
    return app
