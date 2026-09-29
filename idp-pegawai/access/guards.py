"""Small, local authorization guards for the fixed RBAC v1 catalog."""
from collections.abc import Callable, Iterable

from .catalog import CAPABILITIES_BY_ROLE, Capability, ScopeType
from .grants import AccessGrant


class AuthorizationDenied(PermissionError):
    """Raised when an actor has no effective grant for the requested action."""


def require_capability(
    grants: Iterable[AccessGrant],
    capability: Capability,
    *,
    org_unit_ids: Iterable[int] | None = None,
    is_same_or_descendant: Callable[[int, int], bool] | None = None,
    coarse_roles: Iterable[str] | None = None,
) -> bool:
    """Require an effective local grant for ``capability`` and requested scope.

    ``coarse_roles`` is intentionally ignored: entry roles are not detailed
    authorization.  Subtree membership is delegated to the authoritative
    hierarchy predicate when supplied; without it only the root is safe.
    """
    requested = tuple(org_unit_ids or ())
    for grant in grants:
        if not grant.is_effective:
            continue
        if capability not in CAPABILITIES_BY_ROLE.get(grant.role, frozenset()):
            continue
        if grant.scope_type == ScopeType.GLOBAL:
            return True
        if grant.scope_type == ScopeType.ORG_UNIT_SUBTREE and grant.scope_root_id is not None:
            predicate = is_same_or_descendant or (lambda candidate, root: candidate == root)
            if all(predicate(unit_id, grant.scope_root_id) for unit_id in requested):
                return True
    raise AuthorizationDenied("authorization denied")


__all__ = ["AuthorizationDenied", "require_capability"]
