from flask import Flask

from .config import Config
from .extensions import db


def create_app(config_object=None):
    app = Flask(__name__)
    if config_object is None:
        app.config.from_object(Config)
    elif isinstance(config_object, dict):
        app.config.from_object(Config)
        app.config.from_mapping(config_object)
    else:
        app.config.from_object(Config)
        app.config.from_object(config_object)
    db.init_app(app)
    from .api import admin_bp, internal_feed_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(internal_feed_bp)
    return app
