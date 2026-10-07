from flask import Blueprint, current_app, jsonify, request
from idp_pegawai.services.pegawai_sync_service import PegawaiSyncService

sync_bp = Blueprint("sync", __name__, url_prefix="/idp-pegawai/internal/api/v1/sync")

def _authorize():
    authorizer = current_app.config.get("INTERNAL_PROFILE_AUTHORIZER")
    if not callable(authorizer):
        return None, (jsonify({"error":"service token tidak valid","code":"service_token_invalid"}),401)
    try:
        claims = authorizer(request.headers.get("Authorization"), request.headers)
    except Exception as e:
        current_app.logger.error(f"Authorizer decode failed: {e}")
        claims=None
    if not isinstance(claims,dict):
        return None,(jsonify({"error":"service token tidak valid","code":"service_token_invalid"}),401)
    scopes=set(str(claims.get("scope","")).split())
    audience=current_app.config.get("INTERNAL_PROFILE_AUDIENCE","idp-pegawai-internal")
    client=current_app.config.get("INTERNAL_PROFILE_CLIENT","s1-jabar-token-exchange")
    token_audience=claims.get("aud")
    audience_allowed=audience in token_audience if isinstance(token_audience,(list,tuple,set)) else token_audience==audience
    if not audience_allowed or claims.get("azp")!=client or "profile:read" not in scopes:
        return None,(jsonify({"error":"consumer tidak diizinkan","code":"consumer_not_allowed"}),403)
    registrations=current_app.config.get("INTERNAL_PROFILE_REGISTRATIONS")
    registration=registrations.get(str(claims.get("azp"))) if isinstance(registrations,dict) else None
    if not isinstance(registration,dict) or registration.get("status")!="active":
        return None,(jsonify({"error":"consumer tidak diizinkan","code":"consumer_not_allowed"}),403)
    resources=registration.get("allowed_resource_families",[])
    if not isinstance(resources,(list,tuple,set)) or "pegawai-profile" not in resources:
        return None,(jsonify({"error":"profile tidak diizinkan","code":"profile_not_allowed"}),403)
    if registration.get("allowed_field_profile") not in {"pegawai-profile.v1","pegawai-internal"}:
        return None,(jsonify({"error":"profile tidak diizinkan","code":"profile_not_allowed"}),403)
    return claims,None

@sync_bp.get("/pegawai")
def sync_pegawai():
    """Bulk sync snapshot untuk s1-jabar.
    ---
    tags: [consumer-sync]
    parameters:
      - name: updated_since
        in: query
        type: string
      - name: page
        in: query
        type: integer
      - name: per_page
        in: query
        type: integer
    responses:
      200: {description: Bulk pegawai snapshot}
      401: {description: Invalid token}
      403: {description: Not allowed}
    """
    claims,denied=_authorize()
    if denied: return denied
    repo=current_app.config.get("PEGAWAI_REPOSITORY")
    if repo is None:
        return jsonify({"error":"service belum siap","code":"service_token_invalid"}),503
    page=request.args.get("page","1")
    per_page=request.args.get("per_page","100")
    updated_since=request.args.get("updated_since")
    # hash_only mode untuk polling notifikasi ringan
    hash_only = request.args.get("hash_only") in ("1","true","yes")
    try: page=int(page)
    except: page=1
    try: per_page=int(per_page)
    except: per_page=100
    result=PegawaiSyncService(repo).snapshot(updated_since=updated_since, page=page, per_page=per_page)
    if hash_only:
        return jsonify({"meta": result["meta"]})
    return jsonify(result)

@sync_bp.get("/pegawai/hash")
def sync_hash():
    claims,denied=_authorize()
    if denied: return denied
    repo=current_app.config.get("PEGAWAI_REPOSITORY")
    if repo is None:
        return jsonify({"error":"service belum siap","code":"service_token_invalid"}),503
    result=PegawaiSyncService(repo).snapshot(page=1, per_page=1)
    return jsonify({"snapshot_hash": result["meta"]["snapshot_hash"], "total": result["meta"]["total"], "generated_at": result["meta"]["generated_at"], "contract_version": "pegawai-sync.v1"})
