"""Private consumer profile endpoint for the short-term SSO pilot."""
from flask import Blueprint, current_app, jsonify, request

from idp_pegawai.services.profile_service import PegawaiProfileService, ProfileResolutionError

profile_bp = Blueprint("profile", __name__, url_prefix="/idp-pegawai/internal/api/v1/consumer")


def _authorize():
    authorizer = current_app.config.get("INTERNAL_PROFILE_AUTHORIZER")
    if not callable(authorizer):
        return None, (jsonify({"error": "service token tidak valid", "code": "service_token_invalid"}), 401)
    try:
        claims = authorizer(request.headers.get("Authorization"), request.headers)
    except Exception as e:
        current_app.logger.error(f"Authorizer decode failed: {str(e)}")
        claims = None
    if not isinstance(claims, dict):
        return None, (jsonify({"error": "service token tidak valid", "code": "service_token_invalid"}), 401)
    scopes = set(str(claims.get("scope", "")).split())
    audience = current_app.config.get("INTERNAL_PROFILE_AUDIENCE", "idp-pegawai-internal")
    client = current_app.config.get("INTERNAL_PROFILE_CLIENT", "s1-jabar-token-exchange")
    token_audience = claims.get("aud")
    audience_allowed = audience in token_audience if isinstance(token_audience, (list, tuple, set)) else token_audience == audience
    if not audience_allowed or claims.get("azp") != client or "profile:read" not in scopes:
        return None, (jsonify({"error": "consumer tidak diizinkan", "code": "consumer_not_allowed"}), 403)
    registrations = current_app.config.get("INTERNAL_PROFILE_REGISTRATIONS")
    registration = registrations.get(str(claims.get("azp"))) if isinstance(registrations, dict) else None
    # Registration is an authorization boundary, not an optional convenience:
    # a valid JWT from an unregistered client must still be denied.
    if not isinstance(registration, dict) or registration.get("status") != "active":
        return None, (jsonify({"error": "consumer tidak diizinkan", "code": "consumer_not_allowed"}), 403)
    resources = registration.get("allowed_resource_families", [])
    if not isinstance(resources, (list, tuple, set)) or "pegawai-profile" not in resources:
        return None, (jsonify({"error": "profile tidak diizinkan", "code": "profile_not_allowed"}), 403)
    if registration.get("allowed_field_profile") not in {"pegawai-profile.v1", "pegawai-internal"}:
        return None, (jsonify({"error": "profile tidak diizinkan", "code": "profile_not_allowed"}), 403)
    return claims, None


@profile_bp.get("/profile")
def profile():
    """Resolve authenticated consumer subject to an active employee profile.
    ---
    tags: [consumer-profile]
    responses:
      200: {description: Curated employee profile}
      401: {description: Invalid service token}
      403: {description: Consumer or employee not allowed}
      404: {description: Identity not found}
      409: {description: Identity conflict}
    """
    claims, denied = _authorize()
    if denied:
        return denied
    repository = current_app.config.get("PEGAWAI_REPOSITORY")
    if repository is None:
        return jsonify({"error": "service belum siap", "code": "service_token_invalid"}), 503
    try:
        data = PegawaiProfileService(repository).resolve(
            provider=str(claims.get("provider", "keycloak")),
            issuer=str(claims.get("iss", "")),
            subject=str(claims.get("sub", "")),
        )
    except ProfileResolutionError as exc:
        status = {"pegawai_identity_not_found": 404, "pegawai_inactive": 403}.get(exc.code, 409)
        return jsonify({"error": exc.message, "code": exc.code}), status
    # consumer audit log (best-effort, sampling)
    try:
        import random, time as _time, sqlalchemy as sa
        from idp_pegawai.extensions import db as _db
        sample = float(current_app.config.get("CONSUMER_LOG_SAMPLE_RATE", 1.0) or 1.0)
        if sample >= 1.0 or random.random() < sample:
            start = request.environ.get("profile_start_ts")
            latency = int((_time.time() - start) * 1000) if isinstance(start, (int, float)) else None
            _db.session.execute(
                sa.text("INSERT INTO consumer_profile_request_logs (consumer_id, endpoint, http_status, latency_ms, pegawai_uuid) VALUES (:c,:e,:s,:l, CAST(:u AS uuid))"),
                {"c": str(claims.get("azp","")), "e": request.path, "s": 200, "l": latency, "u": str(data.get("uuid") or data.get("pegawai_uuid") or "") or None},
            )
            _db.session.commit()
    except Exception:
        try:
            from idp_pegawai.extensions import db as _db2
            _db2.session.rollback()
        except Exception:
            pass
    return jsonify({"data": data, "meta": {"source": "idp-pegawai", "contract_version": "pegawai-profile.v1"}})


__all__ = ["profile_bp"]

@profile_bp.before_request
def _mark_start():
    import time
    request.environ["profile_start_ts"] = time.time()
