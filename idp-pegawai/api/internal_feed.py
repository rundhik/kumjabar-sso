"""HTTP transport for the curated internal delta feed."""
from flask import Blueprint, current_app, jsonify, request

from idp_pegawai.consumer.cursor import CursorError
from idp_pegawai.consumer.feed import FeedError, PageLimitError

internal_feed_bp = Blueprint("internal_feed", __name__, url_prefix="/internal/feed")


@internal_feed_bp.get("/<resource_family>")
def delta_feed(resource_family):
    code = request.headers.get("X-Consumer-Code")
    registration = current_app.config.get("INTERNAL_FEED_REGISTRATIONS", {}).get(code)
    if registration is None or getattr(registration, "status", "active") in {"revoked", "disabled"}:
        return jsonify({"error": "consumer unauthorized"}), 401
    allowed = getattr(registration, "allowed_resource_families", None)
    if allowed is not None and resource_family not in allowed:
        return jsonify({"error": "resource unauthorized"}), 401
    try:
        raw_limit = request.args.get("limit", "100")
        limit = int(raw_limit) if raw_limit.isdigit() else raw_limit
        page = current_app.config["INTERNAL_FEED_SERVICE"].read(
            registration=registration, resource_family=resource_family,
            limit=limit, cursor=request.args.get("cursor"))
    except PageLimitError as exc:
        return jsonify({"error": str(exc)}), 400
    except CursorError as exc:
        status = 410 if "expired" in str(exc).lower() else 400
        return jsonify({"error": str(exc)}), status
    except FeedError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": page.items, "next_cursor": page.next_cursor})
