from flask import Blueprint, current_app, jsonify

from idp_pegawai.repositories.org_unit_repository import OrgUnitRepository
from idp_pegawai.schemas.org_unit import serialize_org_unit

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/org-units")
def list_org_units():
    repository = current_app.config.get("ORG_UNIT_REPOSITORY")
    if repository is None:
        repository = OrgUnitRepository(current_app.extensions["sqlalchemy"].session)
    units = repository.list_active()
    return jsonify({
        "data": [serialize_org_unit(unit) for unit in units],
        "sync": {"source": "idp-pegawai", "contract_version": "org_units.v1"},
        "meta": {"count": len(units)},
    })
