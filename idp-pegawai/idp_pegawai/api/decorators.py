"""HTTP boundary for the fixed local authorization guards."""
from collections.abc import Callable, Iterable
from functools import wraps
from typing import Any

from flask import jsonify

from idp_pegawai.access.catalog import Capability
from idp_pegawai.access.guards import AuthorizationDenied, require_capability


_SAFE_FORBIDDEN = {"error": "forbidden", "message": "Akses ditolak."}


def require_authorization(
    capability: Capability,
    *,
    grants_getter: Callable[[], Iterable[Any]],
    org_unit_ids: Iterable[int] | None = None,
    is_same_or_descendant: Callable[[int, int], bool] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Require a core capability guard before invoking a Flask view.

    The view supplies effective local grants; coarse identity roles and policy
    expressions are deliberately not accepted at this HTTP boundary. A core
    denial becomes one safe HTTP 403 response without exposing authorization
    internals. Unexpected failures are not rewritten as denials.
    """
    if not callable(grants_getter):
        raise TypeError("grants_getter must be callable")

    def decorate(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                require_capability(
                    grants_getter(),
                    capability,
                    org_unit_ids=org_unit_ids,
                    is_same_or_descendant=is_same_or_descendant,
                )
            except AuthorizationDenied:
                return jsonify(_SAFE_FORBIDDEN), 403
            return view(*args, **kwargs)

        return wrapped

    return decorate


__all__ = ["require_authorization"]
