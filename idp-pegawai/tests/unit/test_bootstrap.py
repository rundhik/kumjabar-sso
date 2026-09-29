from idp_pegawai import create_app
from idp_pegawai.extensions import db


def test_application_factory_initializes_database_extension():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})

    assert app.extensions["sqlalchemy"] is db
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_package_exposes_application_factory():
    assert callable(create_app)


def test_application_factory_returns_flask_app():
    app = create_app()

    assert app.name == "idp_pegawai"
    assert app.config["TESTING"] is False


def test_application_factory_accepts_config_object():
    class TestConfig:
        TESTING = True
        CUSTOM_SETTING = "enabled"

    app = create_app(TestConfig)

    assert app.config["TESTING"] is True
    assert app.config["CUSTOM_SETTING"] == "enabled"
