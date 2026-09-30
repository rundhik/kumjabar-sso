"""Dependency-light security middleware for local and production entry points."""
from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from flask import request


class SlidingWindowLimiter:
    def __init__(self, limit: int = 120, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits = defaultdict(deque)
        self._lock = Lock()

    def allowed(self, key: str) -> bool:
        now = monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window_seconds:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


def init_security(app):
    limiter = SlidingWindowLimiter(
        limit=int(app.config.get("RATE_LIMIT_PER_MINUTE", 120)),
        window_seconds=60,
    )
    app.extensions["rate_limiter"] = limiter

    @app.before_request
    def rate_limit_request():
        # Local development can opt out explicitly; production remains bounded.
        if app.config.get("TESTING") or app.config.get("RATE_LIMIT_DISABLED"):
            return None
        key = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
        if not limiter.allowed(key):
            return {"error": "terlalu banyak permintaan", "code": "rate_limited"}, 429
        return None

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'")
        return response

    return app
