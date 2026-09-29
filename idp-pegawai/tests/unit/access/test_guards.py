from datetime import datetime, timedelta, timezone

import pytest

from idp_pegawai.access.catalog import Capability, Role, ScopeType
from idp_pegawai.access.grants import AccessGrant, GrantStatus
from idp_pegawai.access.guards import AuthorizationDenied, require_capability


def grant(role=Role.VIEWER, scope_type=ScopeType.GLOBAL, scope_root_id=None, valid_until=None):
    return AccessGrant(role, scope_type, scope_root_id, valid_until)


def test_require_capability_denies_by_default():
    with pytest.raises(AuthorizationDenied):
        require_capability([], Capability.PEGAWAI_VIEW)


def test_require_capability_allows_capability_from_effective_grant():
    assert require_capability(
        [grant(Role.VIEWER)], Capability.PEGAWAI_VIEW
    ) is True


def test_require_capability_denies_expired_and_revoked_grants():
    expired = grant(valid_until=datetime.now(timezone.utc) - timedelta(seconds=1))
    revoked = grant()
    object.__setattr__(revoked, "status", GrantStatus.REVOKED)
    with pytest.raises(AuthorizationDenied):
        require_capability([expired], Capability.PEGAWAI_VIEW)
    with pytest.raises(AuthorizationDenied):
        require_capability([revoked], Capability.PEGAWAI_VIEW)


def test_require_capability_denies_scope_mismatch():
    scoped = grant(Role.VIEWER, ScopeType.ORG_UNIT_SUBTREE, 10)
    with pytest.raises(AuthorizationDenied):
        require_capability([scoped], Capability.PEGAWAI_VIEW, org_unit_ids=[20])
    assert require_capability([scoped], Capability.PEGAWAI_VIEW, org_unit_ids=[10]) is True


def test_global_scope_allows_any_requested_unit():
    assert require_capability([grant()], Capability.PEGAWAI_VIEW, org_unit_ids=[999]) is True


def test_subtree_scope_uses_authoritative_descendant_predicate():
    scoped = grant(Role.VIEWER, ScopeType.ORG_UNIT_SUBTREE, 10)
    assert require_capability(
        [scoped], Capability.PEGAWAI_VIEW, org_unit_ids=[20],
        is_same_or_descendant=lambda candidate, root: candidate == 20 and root == 10,
    ) is True


def test_coarse_role_is_not_authority():
    with pytest.raises(AuthorizationDenied):
        require_capability([], Capability.PEGAWAI_VIEW, coarse_roles=["admin"])
