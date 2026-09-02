from flask import Blueprint, current_app, jsonify, request

from idp_pegawai.repositories.org_unit_repository import OrgUnitRepository
from idp_pegawai.repositories.pegawai_repository import PegawaiRepository
from idp_pegawai.schemas.org_unit import serialize_org_unit
from idp_pegawai.schemas.pegawai import serialize_pegawai

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


@admin_bp.get("/pegawai")
def list_pegawai():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page dan per_page harus bilangan positif"}), 400
    if page < 1 or per_page < 1 or per_page > 100:
        return jsonify({"error": "page dan per_page harus bilangan positif"}), 400
    repository = current_app.config.get("PEGAWAI_REPOSITORY")
    if repository is None:
        repository = PegawaiRepository(current_app.extensions["sqlalchemy"].session)
    records = repository.list_active_snapshot_scope()
    query = request.args.get("q", "").strip().casefold()
    if query:
        records = [p for p in records if query in p.nip.casefold() or query in p.nama_lengkap.casefold()]
    total = len(records)
    start = (page - 1) * per_page
    items = records[start:start + per_page]
    pages = (total + per_page - 1) // per_page
    return jsonify({
        "data": [serialize_pegawai(p) for p in items],
        "sync": {"source": "idp-pegawai", "contract_version": "pegawai.v1"},
        "meta": {"page": page, "per_page": per_page, "total": total, "pages": pages},
    })
