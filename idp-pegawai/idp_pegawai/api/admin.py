import requests
import sqlalchemy as sa
from uuid import UUID
from datetime import datetime, timezone
from flask import Blueprint, current_app, jsonify, request, session
from sqlalchemy.exc import IntegrityError

from idp_pegawai.repositories.org_unit_repository import OrgUnitRepository
from idp_pegawai.repositories.pegawai_repository import PegawaiRepository
from idp_pegawai.schemas.org_unit import serialize_org_unit
from idp_pegawai.schemas.pegawai import serialize_pegawai
from idp_pegawai.services.org_unit_service import OrgUnitService
from idp_pegawai.services.pegawai_service import PegawaiService
from idp_pegawai.extensions import db
from idp_pegawai.models.org_unit import OrgUnit
from idp_pegawai.models.pegawai import Pegawai
from idp_pegawai.models.identity_link import PegawaiIdentityLink, PROVIDERS
from idp_pegawai.access.catalog import Capability
from idp_pegawai.access.guards import AuthorizationDenied, require_capability

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _guard(capability=Capability.ACCESS_GRANT_CREATE):
    try: require_capability(current_app.config.get("ADMIN_GRANTS", ()), capability)
    except AuthorizationDenied: return jsonify({"error":"forbidden", "code":"capability_denied"}), 403
    return None

def _get(model, value):
    try: value = UUID(value)
    except (ValueError, TypeError, AttributeError): return None
    query = db.session.query(model).filter_by(uuid=value)
    # Identity links deliberately use an active/link-status lifecycle and do
    # not have the soft-delete column used by Pegawai/OrgUnit.
    if hasattr(model, "deleted_at"):
        query = query.filter_by(deleted_at=None)
    return query.one_or_none()

def _json():
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else {}

def _ensure_identity_link(emp, sub, kc_url, kc_realm):
    """Memastikan baris PegawaiIdentityLink terhubung dengan sub Keycloak terbaru."""
    try:
        # kc_url bisa sudah full issuer (http://localhost:8080/realms/kumjabar) atau base (http://host:8080)
        if "/realms/" in kc_url:
            issuer_str = kc_url.rstrip("/")
        else:
            issuer_str = f"{kc_url.rstrip('/')}/realms/{kc_realm}"
        existing_link = db.session.query(PegawaiIdentityLink).filter_by(
            pegawai_id=emp.id, provider="keycloak"
        ).first()

        if not existing_link:
            # Skenario 1: Belum ada link sama sekali -> Insert baru
            new_link = PegawaiIdentityLink(
                pegawai=emp,
                provider="keycloak",
                issuer=issuer_str,
                provider_subject=sub,
                email=emp.email_dinas or None,
                email_normalized=(emp.email_dinas or "").strip().lower() or None,
                email_verified=True,
                is_active=True,
                linked_at=datetime.now(timezone.utc),
                management_mode="auto_synced",
                link_status="linked",
                link_version=1,
                metadata_={},
            )
            db.session.add(new_link)
            db.session.commit()
        elif existing_link.provider_subject != sub or existing_link.issuer != issuer_str:
            # Skenario 2: Link lama ada tapi sub/issuer berbeda -> Update sub ke yang terbaru!
            existing_link.provider_subject = sub
            existing_link.issuer = issuer_str
            existing_link.email = emp.email_dinas or existing_link.email
            existing_link.email_normalized = (emp.email_dinas or "").strip().lower() or existing_link.email_normalized
            existing_link.linked_at = datetime.now(timezone.utc)
            existing_link.is_active = True
            existing_link.link_status = "linked"
            db.session.commit()
            current_app.logger.info(f"Updated identity link for NIP {emp.nip} with new sub: {sub}")

    except Exception as db_err:
        db.session.rollback()
        current_app.logger.error(f"Gagal auto-link identity untuk NIP {emp.nip}: {str(db_err)}")

@admin_bp.post("/org-units/create")
def create_org_unit():
    """Create an organization unit.\n    ---\n    responses:\n      201:\n        description: Created\n    """
    if (denied := _guard(Capability.ORG_UNIT_CREATE)): return denied
    data = _json()
    if data.get("parent_uuid"):
        parent = _get(OrgUnit, data.pop("parent_uuid"))
        if parent is None: return jsonify({"error":"parent tidak ditemukan"}), 404
        data["parent"] = parent
    try:
        obj = OrgUnitService(db.session).create(**data)
        db.session.commit()
    except (ValueError, KeyError, TypeError) as exc:
        db.session.rollback(); return jsonify({"error":str(exc)}), 400
    return jsonify({"data":serialize_org_unit(obj)}), 201

@admin_bp.patch("/org-units/<uuid>")
def update_org_unit(uuid):
    """Update an organization unit.
    ---
    tags: [Organization Units]
    parameters:
      - in: path
        name: uuid
        required: true
        schema: {type: string, format: uuid}
    responses:
      200: {description: Updated}
      400: {description: Invalid payload}
      404: {description: Unit not found}
    """
    if (denied := _guard(Capability.ORG_UNIT_UPDATE)): return denied
    obj = _get(OrgUnit, uuid)
    if obj is None: return jsonify({"error":"unit tidak ditemukan"}), 404
    data = _json()
    if "parent_uuid" in data:
        parent_uuid = data.pop("parent_uuid")
        if parent_uuid in (None, ""):
            data["parent"] = None
        else:
            parent = _get(OrgUnit, parent_uuid)
            if parent is None: return jsonify({"error":"parent tidak ditemukan", "code":"not_found"}), 404
            if parent.uuid == obj.uuid: return jsonify({"error":"unit tidak dapat menjadi parent dirinya sendiri", "code":"invalid_parent"}), 400
            data["parent"] = parent
    try: OrgUnitService(db.session).update(obj, **data); db.session.commit()
    except (ValueError, TypeError) as exc: db.session.rollback(); return jsonify({"error":str(exc)}), 400
    return jsonify({"data":serialize_org_unit(obj)})

@admin_bp.post("/org-units/<uuid>/deactivate")
def deactivate_org_unit(uuid):
    """Deactivate an organization unit without hard delete.
    ---
    tags: [Organization Units]
    responses:
      200: {description: Deactivated}
      404: {description: Unit not found}
    """
    if (denied := _guard(Capability.ORG_UNIT_DEACTIVATE)): return denied
    obj = _get(OrgUnit, uuid)
    if obj is None: return jsonify({"error":"unit tidak ditemukan"}), 404
    OrgUnitService(db.session).deactivate(obj, _json().get("reason")); db.session.commit()
    return jsonify({"data":serialize_org_unit(obj)})

@admin_bp.post("/pegawai/create")
def create_pegawai():
    """Create an employee.\n    ---\n    responses:\n      201:\n        description: Created\n    """
    if (denied := _guard(Capability.PEGAWAI_CREATE)): return denied
    data = _json()
    if data.get("primary_org_unit_uuid"):
        org = _get(OrgUnit, data.pop("primary_org_unit_uuid"))
        if org is None:
            return jsonify({"error":"unit tidak ditemukan", "code":"not_found"}), 404
        data["primary_org_unit"] = org
    try:
        obj = PegawaiService(db.session).create(**data)
        db.session.commit()
    except (ValueError, KeyError, TypeError) as exc:
        db.session.rollback(); return jsonify({"error":str(exc)}), 400
    return jsonify({"data":serialize_pegawai(obj)}), 201

@admin_bp.patch("/pegawai/<uuid>")
def update_pegawai(uuid):
    """Update mutable employee fields and synchronize lifecycle status.
    ---
    tags: [Pegawai]
    parameters:
      - in: path
        name: uuid
        required: true
        schema: {type: string, format: uuid}
    responses:
      200: {description: Updated}
      400: {description: Invalid payload}
      404: {description: Employee or organization unit not found}
    """
    if (denied := _guard(Capability.PEGAWAI_UPDATE)): return denied
    obj = _get(Pegawai, uuid)
    if obj is None: return jsonify({"error":"pegawai tidak ditemukan"}), 404
    data = _json()
    if "primary_org_unit_uuid" in data:
        org_uuid = data.pop("primary_org_unit_uuid")
        if org_uuid in (None, ""):
            data["primary_org_unit"] = None
        else:
            org = _get(OrgUnit, org_uuid)
            if org is None: return jsonify({"error":"unit tidak ditemukan", "code":"not_found"}), 404
            data["primary_org_unit"] = org
    try:
        PegawaiService(db.session).update(obj, **data)
        db.session.commit()
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc), "code": "invalid_payload"}), 400
    return jsonify({"data":serialize_pegawai(obj)})

@admin_bp.post("/pegawai/<uuid>/deactivate")
def deactivate_pegawai(uuid):
    """Deactivate an employee and retain its record.
    ---
    tags: [Pegawai]
    responses:
      200: {description: Deactivated}
      400: {description: Invalid lifecycle status}
      404: {description: Employee not found}
    """
    if (denied := _guard(Capability.PEGAWAI_DEACTIVATE)): return denied
    obj = _get(Pegawai, uuid)
    if obj is None: return jsonify({"error":"pegawai tidak ditemukan"}), 404
    body = _json()
    try: PegawaiService(db.session).deactivate(obj, body.get("status", "nonaktif"), body.get("reason")); db.session.commit()
    except ValueError as exc: db.session.rollback(); return jsonify({"error":str(exc)}), 400
    return jsonify({"data":serialize_pegawai(obj)})

@admin_bp.get("/pegawai/<uuid>/identity-links")
def list_identity_links(uuid):
    if (denied := _guard(Capability.IDENTITY_LINK_CREATE)): return denied
    pegawai = _get(Pegawai, uuid)
    if pegawai is None:
        return jsonify({"error": "pegawai tidak ditemukan", "code": "not_found"}), 404
    links = db.session.query(PegawaiIdentityLink).filter_by(pegawai_id=pegawai.id, is_active=True).all()
    return jsonify({"data": [{"uuid": str(link.uuid), "provider": link.provider, "issuer": link.issuer,
                               "provider_subject": link.provider_subject, "email": link.email,
                               "email_verified": link.email_verified, "is_active": link.is_active,
                               "link_status": link.link_status} for link in links]})


@admin_bp.post("/pegawai/<uuid>/identity-links")
def create_identity_link(uuid):
    """Create an identity link for an employee."""
    """Create a Keycloak identity link for an employee.
    ---
    tags: [Identity Links]
    responses:
      201: {description: Created}
      400: {description: Invalid or conflicting link}
      404: {description: Employee not found}
    """
    if (denied := _guard(Capability.IDENTITY_LINK_CREATE)): return denied
    pegawai = _get(Pegawai, uuid)
    if pegawai is None:
        return jsonify({"error": "pegawai tidak ditemukan", "code": "not_found"}), 404
    data = _json()
    provider = str(data.get("provider", "")).strip().lower()
    issuer = str(data.get("issuer", "")).strip()
    subject = str(data.get("provider_subject", "")).strip()
    if provider not in PROVIDERS or not issuer or not subject:
        return jsonify({"error": "provider, issuer, dan provider_subject wajib diisi", "code": "invalid_payload"}), 400
    try:
        link = PegawaiIdentityLink(
            pegawai=pegawai, provider=provider, issuer=issuer,
            provider_subject=subject, email=data.get("email") or None,
            email_normalized=(data.get("email") or "").strip().lower() or None,
            email_verified=bool(data.get("email_verified", False)), is_active=True,
            linked_at=datetime.now(timezone.utc), management_mode="idp_managed",
            link_status="linked", link_version=1, metadata_={},
        )
        db.session.add(link)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "sub ini sudah terhubung ke identity link lain", "code": "identity_link_conflict"}), 409
    except (ValueError, TypeError):
        db.session.rollback()
        return jsonify({"error": "data identity link tidak valid", "code": "invalid_payload"}), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Identity link creation failed")
        return jsonify({"error": "identity link gagal disimpan, periksa konfigurasi database", "code": "identity_link_save_failed"}), 500
    return jsonify({"data": {"provider": link.provider, "issuer": link.issuer, "provider_subject": link.provider_subject, "is_active": link.is_active, "link_status": link.link_status}}), 201


@admin_bp.patch("/identity-links/<uuid>")
def update_identity_link(uuid):
    if (denied := _guard(Capability.IDENTITY_LINK_CREATE)): return denied
    link = _get(PegawaiIdentityLink, uuid)
    if link is None or not link.is_active:
        return jsonify({"error": "identity link tidak ditemukan", "code": "not_found"}), 404
    data = _json()
    provider = str(data.get("provider", link.provider)).strip().lower()
    issuer = str(data.get("issuer", link.issuer)).strip()
    subject = str(data.get("provider_subject", link.provider_subject)).strip()
    if provider not in PROVIDERS or not issuer or not subject:
        return jsonify({"error": "provider, issuer, dan provider_subject wajib diisi", "code": "invalid_payload"}), 400
    link.provider, link.issuer, link.provider_subject = provider, issuer, subject
    link.email = data.get("email") or None
    link.email_normalized = (data.get("email") or "").strip().lower() or None
    link.email_verified = bool(data.get("email_verified", link.email_verified))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "sub ini sudah terhubung ke identity link lain", "code": "identity_link_conflict"}), 409
    return jsonify({"data": {"uuid": str(link.uuid), "provider": link.provider, "issuer": link.issuer, "provider_subject": link.provider_subject, "is_active": link.is_active, "link_status": link.link_status}})




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


@admin_bp.get("/org-units/<uuid>")
def get_org_unit(uuid):
    """Get one organization unit by UUID."""
    obj = _get(OrgUnit, uuid)
    if obj is None:
        return jsonify({"error": "unit tidak ditemukan", "code": "not_found"}), 404
    return jsonify({"data": serialize_org_unit(obj)})


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


@admin_bp.get("/pegawai/<uuid>")
def get_pegawai(uuid):
    """Get one employee by UUID using the curated response schema."""
    obj = _get(Pegawai, uuid)
    if obj is None:
        return jsonify({"error": "pegawai tidak ditemukan", "code": "not_found"}), 404
    return jsonify({"data": serialize_pegawai(obj)})

def _get_keycloak_admin_token():
    """Request Keycloak Admin token via client_credentials grant."""
    kc_url = current_app.config.get("KEYCLOAK_URL", "http://kumjabar_keycloak:8080")
    kc_realm = current_app.config.get("KEYCLOAK_REALM", "kumjabar")
    client_id = current_app.config.get("KEYCLOAK_CLIENT_ID", "idp-pegawai-admin")
    client_secret = current_app.config.get("KEYCLOAK_CLIENT_SECRET", "")

    token_url = f"{kc_url}/realms/{kc_realm}/protocol/openid-connect/token"
    try:
        token_res = requests.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=10,
        )
        if token_res.status_code != 200:
            return None, (jsonify({"error": "Gagal autentikasi ke Keycloak Admin API", "code": "kc_auth_failed"}), 502)
        admin_token = token_res.json().get("access_token")
        return admin_token, None
    except Exception as exc:
        return None, (jsonify({"error": f"Koneksi ke Keycloak gagal: {str(exc)}", "code": "kc_connection_error"}), 503)


def _sync_single_employee_record(emp, headers, kc_url, kc_realm):
    """Sync single employee record to Keycloak (upsert logic)."""
    nip = str(emp.nip).strip() if emp.nip else ""
    if not nip:
        return {"status": "skipped", "reason": "nip_empty"}

    emp_attributes = {
        "uuid_idp": [str(emp.uuid)],
        "nip": [nip],
        "nama_lengkap": [emp.nama_lengkap],
        "status_pegawai": [emp.status_pegawai],
        "org_units": [emp.primary_org_unit.code if emp.primary_org_unit else ""]
    }

    users_url = f"{kc_url}/admin/realms/{kc_realm}/users"

    # Cek apakah NIP sudah ada di Keycloak
    try:
        check_res = requests.get(f"{users_url}?username={nip}", headers=headers, timeout=5)
    except Exception as exc:
        return {"status": "failed", "error": f"Koneksi ke Keycloak gagal: {str(exc)}"}

    kc_public = current_app.config.get("KEYCLOAK_PUBLIC_URL", "") or current_app.config.get("INTERNAL_PROFILE_ISSUER", "") or kc_url
    kc_public = kc_public.rstrip("/")

    if check_res.status_code == 200 and len(check_res.json()) > 0:
        # === SKENARIO 1: UPDATE (USER EXISTING) — jangan sentuh email/firstName biar ga trigger UPDATE_PROFILE ===
        existing_user = check_res.json()[0]
        user_id = existing_user["id"]  # sub Keycloak

        updated_attributes = {
            **(existing_user.get("attributes") or {}),
            **emp_attributes
        }

        # Explicit clear requiredActions biar user existing ga disuruh UPDATE_PROFILE lagi
        update_payload = {
            "attributes": updated_attributes,
            "requiredActions": [],
        }

        try:
            put_res = requests.put(
                f"{users_url}/{user_id}",
                json=update_payload,
                headers=headers,
                timeout=5
            )
        except Exception as exc:
            return {"status": "failed", "error": f"Koneksi ke Keycloak gagal: {str(exc)}"}

        if put_res.status_code in (200, 204):
            _ensure_identity_link(emp, user_id, kc_public, kc_realm)
            return {"status": "updated", "user_id": user_id, "action": "updated"}
        else:
            return {"status": "failed", "error": put_res.text, "status_code": put_res.status_code}

    # === SKENARIO 2: INSERT (USER BARU) — hanya user baru yang wajib ganti password ===
    default_password = "PNSJabar2026!"
    user_payload = {
        "username": nip,
        "enabled": True,
        "email": emp.email_dinas or f"{nip}@kumjabar.go.id",
        "firstName": emp.nama_lengkap,
        "credentials": [
            {
                "type": "password",
                "value": default_password,
                "temporary": True
            }
        ],
        "requiredActions": ["UPDATE_PASSWORD"],
        "attributes": emp_attributes
    }

    try:
        create_res = requests.post(users_url, json=user_payload, headers=headers, timeout=5)
    except Exception as exc:
        return {"status": "failed", "error": f"Koneksi ke Keycloak gagal: {str(exc)}"}

    if create_res.status_code == 201:
        # Ambil 'sub' dari Location Header atau via Query
        location_header = create_res.headers.get("Location", "")
        created_sub = location_header.split("/")[-1] if location_header else None

        if not created_sub:
            try:
                get_user = requests.get(f"{users_url}?username={nip}", headers=headers, timeout=5)
                if get_user.status_code == 200 and len(get_user.json()) > 0:
                    created_sub = get_user.json()[0].get("id")
            except Exception:
                pass

        # --- PROSES AUTO-LINKING UNTUK USER BARU ---
        if created_sub:
            _ensure_identity_link(emp, created_sub, kc_public, kc_realm)
        return {"status": "created", "user_id": created_sub, "action": "created"}
    else:
        return {"status": "failed", "error": create_res.text, "status_code": create_res.status_code}


@admin_bp.post("/pegawai/<uuid>/sync-keycloak")
def sync_single_pegawai_to_keycloak(uuid):
    """Sync single employee to Keycloak Realm via Admin REST API.
    ---
    tags: [Pegawai]
    parameters:
      - in: path
        name: uuid
        type: string
        required: true
        description: Employee UUID
    responses:
      200:
        description: Employee successfully synced to Keycloak
      400:
        description: Invalid employee data
      403:
        description: Forbidden - requires employee management capability
      404:
        description: Employee not found
      502:
        description: Keycloak Admin API failure
      503:
        description: Keycloak connection error
    """
    denied_update = _guard(Capability.PEGAWAI_UPDATE)
    denied_create = _guard(Capability.PEGAWAI_CREATE)
    if denied_update and denied_create:
        return denied_update

    emp = _get(Pegawai, uuid)
    if emp is None:
        return jsonify({"error": "pegawai tidak ditemukan", "code": "not_found"}), 404

    nip = str(emp.nip).strip() if emp.nip else ""
    if not nip:
        return jsonify({"error": "Pegawai tidak memiliki NIP valid", "code": "invalid_nip"}), 400

    admin_token, err_response = _get_keycloak_admin_token()
    if err_response:
        return err_response

    kc_url = current_app.config.get("KEYCLOAK_URL", "http://kumjabar_keycloak:8080")
    kc_realm = current_app.config.get("KEYCLOAK_REALM", "kumjabar")
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }

    res = _sync_single_employee_record(emp, headers, kc_url, kc_realm)

    # Best-effort audit log
    actor_id = None
    try:
        actor_id = session.get("user_id") or (int(current_app.config.get("CURRENT_USER_ID") or 0) or None)
    except Exception:
        pass

    created_count = 1 if res.get("status") == "created" else 0
    updated_count = 1 if res.get("status") == "updated" else 0
    failed_count = 1 if res.get("status") == "failed" else 0
    result_status = "success" if failed_count == 0 else "failed"

    try:
        import json
        detail_json = json.dumps({"mode": "single", "pegawai_uuid": str(emp.uuid), "nip": nip, "status": res.get("status")})
        db.session.execute(
            sa.text("INSERT INTO keycloak_sync_logs (actor_user_id, result, created_count, updated_count, skipped_count, failed_count, total_processed, detail) VALUES (:a,:r,:c,:u,:s,:f,:t, CAST(:d AS jsonb))"),
            {
                "a": actor_id,
                "r": result_status,
                "c": created_count,
                "u": updated_count,
                "s": 0,
                "f": failed_count,
                "t": 1,
                "d": detail_json,
            },
        )
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

    if res.get("status") == "failed":
        return jsonify({
            "error": f"Gagal sync ke Keycloak: {res.get('error', 'Terjadi kesalahan pada Keycloak')}",
            "code": "kc_sync_failed"
        }), 502

    return jsonify({
        "data": {
            "action": res.get("action"),
            "pegawai_uuid": str(emp.uuid),
            "nip": nip,
            "nama_lengkap": emp.nama_lengkap,
            "keycloak_sub": res.get("user_id"),
            "status": "success",
        }
    }), 200


@admin_bp.post("/pegawai/sync-keycloak")
def sync_pegawai_to_keycloak():
    """Sync/Upsert active employees to Keycloak Realm via Admin REST API.
    ---
    tags: [Pegawai]
    responses:
      200: {description: Bulk sync completed}
      403: {description: Forbidden}
      502: {description: Keycloak API failure}
      503: {description: Keycloak connection error}
    """
    if (denied := _guard(Capability.PEGAWAI_CREATE)): return denied

    admin_token, err_response = _get_keycloak_admin_token()
    if err_response:
        return err_response

    kc_url = current_app.config.get("KEYCLOAK_URL", "http://kumjabar_keycloak:8080")
    kc_realm = current_app.config.get("KEYCLOAK_REALM", "kumjabar")
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }

    # 2. Ambil seluruh pegawai aktif
    repository = current_app.config.get("PEGAWAI_REPOSITORY")
    if repository is None:
        repository = PegawaiRepository(db.session)
    active_employees = [p for p in repository.list_active_snapshot_scope() if p.status_pegawai == "aktif"]

    created_count = 0
    updated_count = 0
    skipped_count = 0
    failed_count = 0

    for emp in active_employees:
        res = _sync_single_employee_record(emp, headers, kc_url, kc_realm)
        if res.get("status") == "created":
            created_count += 1
        elif res.get("status") == "updated":
            updated_count += 1
            skipped_count += 1
        elif res.get("status") == "skipped":
            pass
        else:
            failed_count += 1

    # audit log (best-effort, jangan gagalkan response)
    try:
        actor_id = None
        try:
            actor_id = session.get("user_id") or (int(current_app.config.get("CURRENT_USER_ID") or 0) or None)
        except Exception:
            pass
        result = "success" if failed_count == 0 else ("partial" if created_count or updated_count else "failed")
        db.session.execute(
            sa.text("INSERT INTO keycloak_sync_logs (actor_user_id, result, created_count, updated_count, skipped_count, failed_count, total_processed, detail) VALUES (:a,:r,:c,:u,:s,:f,:t, CAST(:d AS jsonb))"),
            {"a": actor_id, "r": result, "c": created_count, "u": updated_count, "s": skipped_count, "f": failed_count, "t": len(active_employees), "d": "{}"},
        )
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

    return jsonify({
        "data": {
            "total_processed": len(active_employees),
            "created": created_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "failed": failed_count,
        }
    }), 200
