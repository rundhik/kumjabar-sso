import pytest
from flask import Flask

from idp_pegawai.access.catalog import Capability, Role, ScopeType
from idp_pegawai.access.grants import AccessGrant
from idp_pegawai.api.decorators import require_authorization


def grant():
    return AccessGrant(Role.VIEWER, ScopeType.GLOBAL)


def test_decorator_allows_when_core_guard_allows():
    app = Flask(__name__)

    @app.get("/resource")
    @require_authorization(Capability.PEGAWAI_VIEW, grants_getter=lambda: [grant()])
    def resource():
        return {"ok": True}

    response = app.test_client().get("/resource")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True}


def test_decorator_translates_denial_to_safe_http_403():
    app = Flask(__name__)

    @app.get("/resource")
    @require_authorization(Capability.PEGAWAI_VIEW, grants_getter=lambda: [])
    def resource():
        return {"ok": True}

    response = app.test_client().get("/resource")
    assert response.status_code == 403
    assert response.get_json() == {"error": "forbidden", "message": "Akses ditolak."}
    assert "grant" not in response.get_data(as_text=True)


def test_decorator_preserves_wrapped_function_metadata():
    app = Flask(__name__)

    @app.get("/resource")
    @require_authorization(Capability.PEGAWAI_VIEW, grants_getter=lambda: [grant()])
    def resource():
        """safe endpoint"""
        return "ok"

    assert resource.__name__ == "resource"
    assert resource.__doc__ == "safe endpoint"


def test_decorator_requires_explicit_grants_getter():
    with pytest.raises(TypeError):
        require_authorization(Capability.PEGAWAI_VIEW)


def test_decorator_does_not_accept_policy_dsl():
    with pytest.raises(TypeError):
        require_authorization(Capability.PEGAWAI_VIEW, policy={"allow": True})
