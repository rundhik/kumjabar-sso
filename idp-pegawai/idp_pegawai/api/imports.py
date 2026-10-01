"""HTTP boundary for safe, local import workflow; no remote identity calls."""
from pathlib import Path
from uuid import UUID
import csv
from io import BytesIO

from flask import Blueprint, current_app, jsonify, request, send_file

from idp_pegawai.access.catalog import Capability
from idp_pegawai.access.guards import AuthorizationDenied, require_capability
from idp_pegawai.extensions import db
from idp_pegawai.imports.intake import IntakeError, intake_file
from idp_pegawai.imports.validation import validate_rows
from idp_pegawai.imports.dry_run import build_dry_run_plan
from idp_pegawai.imports.apply import apply_with_outbox
from idp_pegawai.imports.error_workbook import build_error_workbook, build_import_template
from idp_pegawai.models.import_batch import ImportBatch
from idp_pegawai.models.outbox_event import OutboxEvent
from idp_pegawai.models.org_unit import OrgUnit
from idp_pegawai.models.pegawai import Pegawai
from idp_pegawai.services.pegawai_service import PegawaiService


def _apply_rows(batch):
    rows = _rows(batch)
    service = PegawaiService(db.session)
    created = updated = noop = 0
    for row in rows:
        existing = db.session.query(Pegawai).filter_by(nip=str(row.get("nip", ""))).one_or_none()
        org = db.session.query(OrgUnit).filter_by(code=str(row.get("org_unit_code", "")), is_active=True, deleted_at=None).one_or_none()
        if org is None:
            raise ValueError("organisasi tidak ditemukan")
        active = str(row.get("status_pegawai", "")).strip().lower() == "aktif"
        values = {
            "nip": str(row.get("nip", "")).strip(),
            "nama_lengkap": str(row.get("nama_lengkap", "")).strip(),
            "email_dinas": row.get("email_dinas") or None,
            "email_google": row.get("email_google") or None,
            "status_pegawai": str(row.get("status_pegawai", "")).strip(),
            "is_active": active,
            "primary_org_unit": org,
        }
        if existing is None:
            service.create(**values); created += 1
        else:
            # Route updates through the domain service so normalization and
            # lifecycle invariants are identical to manual CRUD.
            service.update(existing, **{k: v for k, v in values.items() if k != "nip"})
            updated += 1
    return {"created": created, "updated": updated, "noop": noop}


def _apply_callback(batch, summary):
    result = _apply_rows(batch)
    summary.update(result)
    return result


__all__ = ["import_bp"]

import_bp = Blueprint("imports", __name__, url_prefix="/imports")
_MAPPING_FIELDS = frozenset({"nip", "nama_lengkap", "status_pegawai", "org_unit_code", "email_dinas", "email_google", "is_active"})


def _guard(capability):
    grants = current_app.config.get("IMPORT_GRANTS", ())
    # Support local/test config where grants are bare Capability enums.
    # Use value-based detection to survive dual-module imports (access vs idp_pegawai.access).
    if grants and all(not hasattr(g, "role") for g in grants):
        cap_value = getattr(capability, "value", str(capability))
        grant_values = {getattr(g, "value", str(g)) for g in grants}
        return None if cap_value in grant_values else (jsonify({"error":"forbidden","code":"capability_denied"}), 403)
    # Handle empty/mixed grants via the canonical guard (fail-closed on non-grant objects).
    try: require_capability(grants, capability)
    except AuthorizationDenied: return jsonify({"error":"forbidden","code":"capability_denied"}), 403
    return None


def _error(message, status, code="invalid_request"):
    return jsonify({"error": message, "code": code}), status


def _find(batch_uuid):
    batch = db.session.query(ImportBatch).filter_by(uuid=batch_uuid).one_or_none()
    return (batch, None) if batch else (None, _error("batch tidak ditemukan", 404, "not_found"))


def _rows(batch):
    path = Path(current_app.config["IMPORT_STORAGE_DIR"]) / batch.storage_key
    if batch.source_format == "csv":
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            return [{target: row.get(source, "") for target, source in batch.mapping_snapshot.items()} for row in reader]
    try:
        from openpyxl import load_workbook
        # Storage keys are opaque and intentionally have no filename suffix;
        # pass a binary stream so openpyxl uses the XLSX ZIP signature instead
        # of rejecting the path based on its extension.
        with path.open("rb") as stream:
            sheet = load_workbook(stream, read_only=True, data_only=True).active
            # Consume the lazy worksheet iterator while the backing stream is open.
            values = list(sheet.values)
        if not values: return []
        headers = [str(x or "") for x in values[0]]
        return [{target: (row[headers.index(source)] if source in headers and headers.index(source) < len(row) else "") for target, source in batch.mapping_snapshot.items()} for row in values[1:]]
    except (ImportError, OSError, ValueError):
        raise ValueError("format XLSX tidak dapat dibaca")


@import_bp.get("/template")
def download_template():
    """Download an XLSX import template with valid reference dropdowns.
    ---
    tags: [imports]
    responses: {200: {description: XLSX template}, 403: {description: Denied}}
    """
    denied = _guard(Capability.IMPORT_VIEW)
    if denied:
        return denied
    codes = current_app.config.get("IMPORT_ORG_CODES", ())
    content = build_import_template(org_units=codes)
    return send_file(BytesIO(content), as_attachment=True, download_name="template-import-pegawai.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@import_bp.post("/batches")
def register_batch():
    """Register CSV/XLSX upload without returning payload or storage key.
    ---
    tags: [imports]
    responses: {201: {description: Batch registered}, 403: {description: Denied}, 415: {description: Invalid upload}}
    """
    denied = _guard(Capability.IMPORT_UPLOAD)
    if denied: return denied
    upload = request.files.get("file")
    if upload is None or not upload.filename: return _error("file wajib diisi", 400)
    storage_dir = current_app.config.get("IMPORT_STORAGE_DIR")
    if not storage_dir: return _error("import persistence belum dikonfigurasi", 503, "import_unavailable")
    try:
        result = intake_file(upload.stream, upload.filename, upload.mimetype, Path(storage_dir), max_size=int(current_app.config.get("IMPORT_MAX_SIZE", 10*1024*1024)))
        uploader = (request.headers.get("X-Actor-Id") or "").strip() if request.headers.get("X-Actor-Id") else ""
        # prefer session username (set by api/auth.py login)
        try:
            from flask import session as _sess
            uploader = (str(_sess.get("username") or "").strip() or uploader)
        except Exception:
            pass
        if not uploader:
            uploader = "unknown"
        batch = ImportBatch(source_format=result.format, original_filename=result.original_filename, file_hash=result.sha256, storage_key=result.storage_key, uploaded_by=uploader)
        db.session.add(batch); db.session.commit()
    except IntakeError as exc: return _error(str(exc), 415, "invalid_upload")
    except Exception:
        db.session.rollback(); current_app.logger.exception("import batch registration failed"); return _error("import persistence gagal", 503, "import_unavailable")
    return jsonify({"data":{"batch_id":str(batch.uuid),"status":batch.status,"source_format":batch.source_format},"meta":{"contract_version":"imports.v1"}}), 201


@import_bp.get("/batches/<uuid:batch_uuid>")
def batch_status(batch_uuid):
    """Return curated batch metadata only. No storage key or source data.
    ---
    tags: [imports]
    responses: {200: {description: Batch status}, 403: {description: Denied}, 404: {description: Batch not found}}
    """
    denied = _guard(Capability.IMPORT_VIEW)
    if denied: return denied
    try: batch, error = _find(batch_uuid)
    except Exception: current_app.logger.exception("import status query failed"); return _error("import persistence gagal",503,"import_unavailable")
    if error: return error
    return jsonify({"data":{"batch_id":str(batch.uuid),"status":batch.status,"source_format":batch.source_format,"summary":batch.summary or {}},"meta":{"contract_version":"imports.v1"}})


@import_bp.get("/batches")
def list_batches():
    """Daftar semua batch (kurasi, tanpa storage key)."""
    denied = _guard(Capability.IMPORT_VIEW)
    if denied:
        return denied
    try:
        batches = db.session.query(ImportBatch).order_by(ImportBatch.created_at.desc()).all()
    except Exception:
        current_app.logger.exception("list batches failed")
        return _error("import persistence gagal", 503, "import_unavailable")
    data = [{"batch_id": str(b.uuid), "status": b.status, "source_format": b.source_format, "created_at": b.created_at.isoformat() if b.created_at else None, "original_filename": b.original_filename, "uploader": b.uploaded_by} for b in batches]
    return jsonify({"data": data, "meta": {"contract_version": "imports.v1"}})


@import_bp.post("/batches/<uuid:batch_uuid>/mapping")
def set_mapping(batch_uuid):
    """Set fixed canonical mapping; source columns must exist in CSV/XLSX.
    ---
    tags: [imports]
    responses: {200: {description: Mapping accepted}, 400: {description: Invalid mapping}, 409: {description: Invalid status}}
    """
    denied = _guard(Capability.IMPORT_MAPPING)
    if denied:
        denied2 = _guard(Capability.IMPORT_VALIDATE)
        if denied2:
            return denied
    batch, error = _find(batch_uuid)
    if error: return error
    if batch.status != "received": return _error("status batch tidak dapat dipetakan",409,"invalid_status")
    mapping = (request.get_json(silent=True) or {}).get("mapping")
    if not isinstance(mapping, dict) or not mapping or set(mapping)-_MAPPING_FIELDS or any(not isinstance(v,str) or not v.strip() for v in mapping.values()): return _error("mapping tidak valid",400,"invalid_mapping")
    try:
        if batch.source_format == "csv":
            with (Path(current_app.config["IMPORT_STORAGE_DIR"])/batch.storage_key).open(newline="",encoding="utf-8-sig") as s: headers=set(next(csv.reader(s),[]))
        else:
            from openpyxl import load_workbook
            with (Path(current_app.config["IMPORT_STORAGE_DIR"]) / batch.storage_key).open("rb") as stream:
                headers={str(x or "") for x in next(load_workbook(stream, read_only=True, data_only=True).active.values, ())}
    except Exception: return _error("mapping tidak valid",400,"invalid_mapping")
    if any(source not in headers for source in mapping.values()): return _error("mapping tidak valid",400,"invalid_mapping")
    batch.mapping_snapshot=mapping; batch.status="mapped"; db.session.commit()
    return jsonify({"data":{"batch_id":str(batch.uuid),"status":batch.status,"mapped_fields":sorted(mapping)}})


@import_bp.post("/batches/<uuid:batch_uuid>/dry-run")
def dry_run(batch_uuid):
    """Validate mapped CSV/XLSX and persist curated summary.
    ---
    tags: [imports]
    responses: {200: {description: Validation result}, 403: {description: Denied}, 404: {description: Batch not found}, 409: {description: Invalid batch status}, 422: {description: Invalid file data}}
    """
    denied = _guard(Capability.IMPORT_VALIDATE)
    if denied: return denied
    batch,error=_find(batch_uuid)
    if error:return error
    if batch.status!="mapped":return _error("status batch belum siap dry-run",409,"invalid_status")
    try:
        rows=_rows(batch); validation=validate_rows(rows,current_app.config.get("IMPORT_ORG_CODES",()),headers=batch.mapping_snapshot.keys()); plan=build_dry_run_plan(rows,validation=validation)
        errors=[{"code":i.code,"severity":i.severity,"row":i.row_number,"field":i.field,"message":i.message} for i in validation.issues]
        batch.summary={**plan.summary,"error_count":len(errors),"errors":errors}; batch.status="staging" if not validation.blocking else "mapped"; db.session.commit()
        return jsonify({"data":{"batch_id":str(batch.uuid),"status":batch.status,"summary":plan.summary,"errors":errors}})
    except Exception: return _error("dry-run gagal",422,"dry_run_invalid")


@import_bp.get("/batches/<uuid:batch_uuid>/error-report")
def error_report(batch_uuid):
    """Download a curated XLSX error report for a completed dry-run.
    ---
    tags: [imports]
    responses: {200: {description: XLSX report}, 403: {description: Denied}, 404: {description: Not found}}
    """
    denied=_guard(Capability.IMPORT_ERROR_WORKBOOK_DOWNLOAD)
    if denied:return denied
    batch,error=_find(batch_uuid)
    if error:return error
    if batch.status not in ("mapped","staging"):return _error("error report belum tersedia",409,"invalid_status")
    try:
        artifact=build_error_workbook(_rows(batch), validate_rows(_rows(batch),current_app.config.get("IMPORT_ORG_CODES",()),headers=batch.mapping_snapshot.keys()), parent_batch_uuid=batch.uuid, root_batch_uuid=batch.root_batch_uuid, org_units=current_app.config.get("IMPORT_ORG_CODES",()))
        return send_file(BytesIO(artifact.content), as_attachment=True, download_name="import-errors.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception:return _error("error report tidak tersedia",422,"report_unavailable")


@import_bp.route("/batches/<uuid:batch_uuid>/preview", methods=["GET", "POST"])
def preview(batch_uuid):
    """Return a bounded, non-sensitive preview after a successful dry-run.
    ---
    tags: [imports]
    responses: {200: {description: Safe preview}, 403: {description: Denied}, 404: {description: Not found}, 409: {description: Invalid status}}
    """
    denied=_guard(Capability.IMPORT_PREVIEW)
    if denied:
        denied2=_guard(Capability.IMPORT_VALIDATE)
        if denied2: return denied
    batch,error=_find(batch_uuid)
    if error:return error
    if batch.status not in ("mapped","staging","ready_to_apply"):return _error("batch belum siap preview",409,"invalid_status")
    summary = batch.summary or {}
    rows = _rows(batch)[:100]
    errors = summary.get("errors", [])
    row_count = sum(int(summary.get(key, 0)) for key in ("planned_create", "planned_update", "planned_noop", "planned_reject")) or len(rows)
    safe_rows = [{field: row.get(field) for field in sorted(batch.mapping_snapshot)} for row in rows]
    return jsonify({"data":{"batch_id":str(batch.uuid),"status":batch.status,"summary":summary,"preview":{"fields":sorted(batch.mapping_snapshot),"row_count":row_count,"rows":safe_rows,"errors":errors}},"meta":{"contract_version":"imports.v1"}})


@import_bp.post("/batches/<uuid:batch_uuid>/approve")
def approve_batch(batch_uuid):
    """Approve a staging batch for atomic apply; approval is local only.
    ---
    tags: [imports]
    responses: {200: {description: Approved}, 403: {description: Denied}, 409: {description: Invalid status}}
    """
    denied = _guard(Capability.IMPORT_APPROVE)
    if denied:
        return denied
    batch, error = _find(batch_uuid)
    if error:
        return error
    if batch.status == "applied":
        return _error("batch sudah diterapkan", 409, "already_applied")
    if batch.status == "ready_to_apply":
        return jsonify({"data": {"batch_id": str(batch.uuid), "status": batch.status}})
    if batch.status != "staging":
        return _error("batch belum siap disetujui", 409, "invalid_status")
    batch.status = "ready_to_apply"
    batch.summary = {**(batch.summary or {}), "approved": True}
    db.session.commit()
    return jsonify({"data": {"batch_id": str(batch.uuid), "status": batch.status, "summary": batch.summary}})


@import_bp.post("/batches/<uuid:batch_uuid>/apply")
def apply_batch(batch_uuid):
    """Atomically finalize validated batch and enqueue a curated outbox event; no remote call.
    ---
    tags: [imports]
    responses: {200: {description: Applied}, 403: {description: Denied}, 409: {description: Invalid status}}
    """
    denied=_guard(Capability.IMPORT_APPLY_DISSETUJUI)
    if denied:return denied
    batch,error=_find(batch_uuid)
    if error:return error
    if batch.status == "applied": return _error("batch sudah diterapkan",409,"already_applied")
    if batch.status not in ("staging","ready_to_apply"):return _error("batch belum siap diterapkan",409,"invalid_status")
    try:
        summary=batch.summary or {}
        apply_with_outbox(batch, lambda: _apply_callback(batch, summary), session=db.session, batch_uuid=batch.uuid, result_summary=summary)
        db.session.commit()
        return jsonify({"data":{"batch_id":str(batch.uuid),"status":batch.status,"summary":summary}})
    except Exception:
        db.session.rollback(); current_app.logger.exception("import apply failed"); return _error("apply gagal",409,"apply_failed")

__all__=["import_bp"]
