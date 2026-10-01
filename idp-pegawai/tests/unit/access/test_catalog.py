import pytest

from idp_pegawai.access.catalog import (
    CAPABILITIES_BY_ROLE,
    ROLE_CATALOG_VERSION,
    ROLE_SCOPE_RULES,
    Capability,
    Role,
    ScopeType,
)


def test_catalog_is_fixed_and_contains_final_roles():
    assert ROLE_CATALOG_VERSION == "v1"
    assert tuple(Role) == (
        Role.VIEWER, Role.IMPORT_OPERATOR, Role.IMPORT_APPROVER,
        Role.ACCESS_ADMIN, Role.AUDITOR, Role.SECURITY_ADMIN,
    )
    assert set(CAPABILITIES_BY_ROLE) == set(Role)
    assert Role.SECURITY_ADMIN not in (Role.ACCESS_ADMIN,)


def test_capabilities_are_namespaced_and_mapping_is_not_empty():
    assert all(cap.value.startswith("idp.") for cap in Capability)
    assert Capability.IMPORT_APPLY_DISSETUJUI not in CAPABILITIES_BY_ROLE[Role.IMPORT_OPERATOR]
    assert Capability.IMPORT_APPROVE_HIGH_IMPACT in CAPABILITIES_BY_ROLE[Role.IMPORT_APPROVER]
    assert Capability.SECURITY_BOOTSTRAP_RECOVER in CAPABILITIES_BY_ROLE[Role.SECURITY_ADMIN]
    assert Capability.IMPORT_UPLOAD not in CAPABILITIES_BY_ROLE[Role.SECURITY_ADMIN]


def test_scope_catalog_allows_only_global_or_subtree_and_security_is_global_only():
    assert tuple(ScopeType) == (ScopeType.GLOBAL, ScopeType.ORG_UNIT_SUBTREE)
    assert ROLE_SCOPE_RULES[Role.SECURITY_ADMIN] == frozenset({ScopeType.GLOBAL})
    assert ROLE_SCOPE_RULES[Role.VIEWER] == frozenset(ScopeType)


def test_catalog_does_not_expose_policy_dsl():
    assert not hasattr(__import__("idp_pegawai.access.catalog", fromlist=["x"]), "evaluate_policy")


def test_unknown_role_is_rejected():
    with pytest.raises(ValueError):
        Role("custom")


def test_catalog_values_match_scoped_grant_contract():
    assert Capability.ACCESS_GRANT_CREATE.value == "idp.access_grant.create"
    assert Capability.ACCESS_GRANT_CRITICAL_APPROVE.value == "idp.access_grant.kritis.approve"
    assert Capability.AUDIT_EXPORT_MASKED.value == "idp.audit.export_masked"
    assert Capability.IMPORT_ERROR_WORKBOOK_DOWNLOAD.value == "idp.import.error_workbook.download"


from idp_pegawai.access.grants import AccessGrant, GrantStatus


def test_scoped_grant_has_explicit_lifecycle_and_rejects_invalid_scope():
    grant = AccessGrant(role=Role.VIEWER, scope_type=ScopeType.GLOBAL)
    assert grant.status is GrantStatus.ACTIVE
    assert grant.is_effective is True
    with pytest.raises(ValueError):
        AccessGrant(role=Role.SECURITY_ADMIN, scope_type=ScopeType.ORG_UNIT_SUBTREE)
    with pytest.raises(ValueError):
        AccessGrant(role=Role.VIEWER, scope_type=ScopeType.GLOBAL, status=GrantStatus.REVOKED)
        

def test_critical_grant_requires_expiry():
    with pytest.raises(ValueError):
        AccessGrant(role=Role.SECURITY_ADMIN, scope_type=ScopeType.GLOBAL)
    grant = AccessGrant(role=Role.SECURITY_ADMIN, scope_type=ScopeType.GLOBAL, valid_until=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))
    assert grant.valid_until is not None
