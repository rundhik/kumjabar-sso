import pytest


@pytest.fixture
def app():
    from idp_pegawai import create_app

    return create_app({
        "TESTING": True,
        "INTERNAL_PROFILE_CLIENT": "s1-jabar-token-exchange",
        "INTERNAL_PROFILE_REGISTRATIONS": {
            "s1-jabar-token-exchange": {
                "status": "active",
                "allowed_resource_families": ["pegawai-profile"],
                "allowed_field_profile": "pegawai-profile.v1",
            }
        },
    })


@pytest.fixture
def client(app):
    return app.test_client()
