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


def _dashboard_stats():
    stats = {"pegawai": 0, "organisasi": 0, "batch_staging": 0, "batch_applied": 0, "batch_error": 0, "kc_logs": 0, "consumer_logs": 0}
    for k, cfg in [("pegawai", "PEGAWAI_REPOSITORY"), ("organisasi", "ORG_UNIT_REPOSITORY")]:
        repo = current_app.config.get(cfg)
        if repo is not None:
            try:
                stats[k] = len(list(repo.list_active_snapshot_scope() if k == "pegawai" else repo.list_active()))
            except Exception:
                pass
    # import_batches via DB if available
    dsn = current_app.config.get("DATABASE_URL") or current_app.config.get("DB_DSN")
    if dsn:
        try:
            import psycopg
            with psycopg.connect(dsn) as conn:
                with conn.cursor() as cur:
                    for tbl, key in [("import_batches", None), ("keycloak_sync_logs", "kc_logs"), ("consumer_profile_request_logs", "consumer_logs")]:
                        try:
                            if key is None:
                                cur.execute("SELECT status, COUNT(*) FROM import_batches GROUP BY status")
                                for s, c in cur.fetchall():
                                    s_norm = str(s).strip().lower()
                                    if s_norm == "staging": stats["batch_staging"] = c
                                    elif s_norm == "applied": stats["batch_applied"] = c
                                    elif s_norm in ("error", "failed"): stats["batch_error"] = c
                            else:
                                cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                                stats[key] = cur.fetchone()[0]
                        except Exception:
                            conn.rollback()
        except Exception:
            pass
    return stats

@ui_bp.get("")
@login_required
def dashboard():
    if not _allowed(Capability.DASHBOARD_VIEW):
        return _denied()
    return render_template("ui/dashboard.html", stats=_dashboard_stats())


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
    return render_template("ui/import.html", supported=supported, current_role=str(session.get("role") or "").lower())


__all__ = ["ui_bp"]
