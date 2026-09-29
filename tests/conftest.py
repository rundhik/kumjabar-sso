import pytest


@pytest.fixture
def app():
    from idp_pegawai import create_app

    return create_app({
        "TESTING": True,
        "INTERNAL_PROFILE_REGISTRATIONS": {
            "s1-feed": {
                "status": "active",
                "allowed_resource_families": ["pegawai-profile"],
                "allowed_field_profile": "pegawai-profile.v1",
            }
        },
    })


@pytest.fixture
def client(app):
    return app.test_client()
