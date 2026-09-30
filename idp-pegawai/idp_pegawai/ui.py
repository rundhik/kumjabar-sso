"""Server-rendered internal admin UI; read-only and deny-by-default."""
from flask import Blueprint, current_app, render_template, session

from idp_pegawai.access.catalog import Capability
from idp_pegawai.access.guards import AuthorizationDenied, require_capability
from idp_pegawai.api.auth import login_required

ui_bp = Blueprint("ui", __name__, url_prefix="/ui")


def _grants():
    return current_app.config.get("UI_GRANTS", ())


def _allowed(capability):
    grants = _grants()
    # Development: UI_GRANTS berisi Capability enum (bukan AccessGrant)
    if grants and all(not hasattr(g, "role") for g in grants):
        cap_value = getattr(capability, "value", str(capability))
        grant_values = {getattr(g, "value", str(g)) for g in grants}
        return cap_value in grant_values
    try:
        require_capability(grants, capability)
        return True
    except AuthorizationDenied as exc:
        try:
            current_app.logger.warning("UI deny %s: grants=%s err=%s", capability, grants, exc)
        except Exception:
            pass
        return False


def _denied():
    return render_template("ui/denied.html"), 403


def _repository_records(config_key, method_name):
    """Read UI data without exposing backend exception details."""
    repo = current_app.config.get(config_key)
    if repo is None:
        return [], None
    try:
        return list(getattr(repo, method_name)()), None
    except Exception:
        current_app.logger.exception("UI repository read failed")
        return [], "error"


@ui_bp.get("")
@login_required
def dashboard():
    if not _allowed(Capability.DASHBOARD_VIEW):
        return _denied()
    return render_template("ui/dashboard.html")


@ui_bp.get("/pegawai")
@login_required
def pegawai():
    if not _allowed(Capability.PEGAWAI_VIEW):
        return _denied()
    records, state = _repository_records("PEGAWAI_REPOSITORY", "list_active_snapshot_scope")
    counts = {"aktif": 0, "nonaktif": 0, "mutasi_keluar": 0, "pensiun": 0, "meninggal": 0}
    for record in records:
        counts[record.status_pegawai] = counts.get(record.status_pegawai, 0) + 1
    units, unit_state = _repository_records("ORG_UNIT_REPOSITORY", "list_active")
    if state is None and unit_state is not None:
        state = unit_state
    return render_template("ui/pegawai.html", records=records, units=units, state=state, status_counts=counts)


@ui_bp.get("/organisasi")
@login_required
def organisasi():
    if not _allowed(Capability.ORG_UNIT_VIEW):
        return _denied()
    units, state = _repository_records("ORG_UNIT_REPOSITORY", "list_active")
    return render_template("ui/organisasi.html", units=units, parent_units=units, state=state)


@ui_bp.get("/import")
@login_required
def import_page():
    if not _allowed(Capability.IMPORT_VIEW):
        return _denied()
    supported = bool(current_app.config.get("IMPORT_STORAGE_DIR"))
    return render_template("ui/import.html", supported=supported)


__all__ = ["ui_bp"]
