import pytest


@pytest.fixture
def app():
    from idp_pegawai import create_app

    return create_app({"TESTING": True})


@pytest.fixture
def client(app):
    return app.test_client()
