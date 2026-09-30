"""Small, explicit text safety helpers for operator-facing input."""
from __future__ import annotations

import html
import re

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(value: object, *, max_length: int = 255) -> str:
    """Normalize control characters and HTML-escape untrusted display text.

    Templates must still use Jinja autoescape; this helper is for values that
    are persisted or echoed into JSON/log-safe operator messages.
    """
    text = "" if value is None else str(value)
    text = _CONTROL_CHARS.sub("", text).strip()
    return html.escape(text[:max_length], quote=True)
