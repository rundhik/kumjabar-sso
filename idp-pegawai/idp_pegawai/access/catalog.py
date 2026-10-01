"""Fixed, versioned RBAC v1 catalog for IDP Pegawai."""
from enum import Enum

ROLE_CATALOG_VERSION = "v1"


class Role(str, Enum):
    VIEWER = "viewer"
    IMPORT_OPERATOR = "import_operator"
    IMPORT_APPROVER = "import_approver"
    ACCESS_ADMIN = "access_admin"
    AUDITOR = "auditor"
    SECURITY_ADMIN = "security_admin"


class ScopeType(str, Enum):
    GLOBAL = "global"
    ORG_UNIT_SUBTREE = "org_unit_subtree"


class Capability(str, Enum):
    DASHBOARD_VIEW = "idp.dashboard.view"
    ORG_UNIT_VIEW = "idp.org_unit.view"
    PEGAWAI_VIEW = "idp.pegawai.view"
    ORG_UNIT_CREATE = "idp.org_unit.create"
    ORG_UNIT_UPDATE = "idp.org_unit.update"
    ORG_UNIT_DEACTIVATE = "idp.org_unit.deactivate"
    PEGAWAI_CREATE = "idp.pegawai.create"
    PEGAWAI_UPDATE = "idp.pegawai.update"
    PEGAWAI_DEACTIVATE = "idp.pegawai.deactivate"
    IDENTITY_LINK_CREATE = "idp.identity_link.create"
    IMPORT_VIEW = "idp.import.view"
    IMPORT_TEMPLATE_DOWNLOAD = "idp.import.template.download"
    IMPORT_UPLOAD = "idp.import.upload"
    IMPORT_MAPPING = "idp.import.mapping"
    IMPORT_PREVIEW = "idp.import.preview"
    IMPORT_VALIDATE = "idp.import.validate"
    IMPORT_ERROR_WORKBOOK_DOWNLOAD = "idp.import.error_workbook.download"
    IMPORT_APPLY_DISSETUJUI = "idp.import.apply_disetujui"
    IMPORT_APPROVE = "idp.import.approve"
    IMPORT_APPROVE_HIGH_IMPACT = "idp.import.approve_high_impact"
    ACCESS_GRANT_VIEW = "idp.access_grant.view"
    ACCESS_GRANT_CREATE = "idp.access_grant.create"
    ACCESS_GRANT_REVOKE = "idp.access_grant.revoke"
    ACCESS_GRANT_CRITICAL_REQUEST = "idp.access_grant.kritis.permintaan"
    ACCESS_GRANT_CRITICAL_APPROVE = "idp.access_grant.kritis.approve"
    AUDIT_VIEW = "idp.audit.view"
    AUDIT_EXPORT_MASKED = "idp.audit.export_masked"
    AUDIT_VERIFY_INTEGRITY = "idp.audit.verify_integrity"
    SECURITY_BOOTSTRAP_RECOVER = "idp.security.bootstrap_recover"


CAPABILITIES_BY_ROLE = {
    Role.VIEWER: frozenset({Capability.DASHBOARD_VIEW, Capability.ORG_UNIT_VIEW, Capability.PEGAWAI_VIEW}),
    Role.IMPORT_OPERATOR: frozenset({Capability.DASHBOARD_VIEW, Capability.ORG_UNIT_VIEW, Capability.PEGAWAI_VIEW, Capability.IMPORT_VIEW, Capability.IMPORT_TEMPLATE_DOWNLOAD, Capability.IMPORT_UPLOAD, Capability.IMPORT_MAPPING, Capability.IMPORT_PREVIEW, Capability.IMPORT_VALIDATE, Capability.IMPORT_ERROR_WORKBOOK_DOWNLOAD, Capability.IMPORT_APPLY_DISSETUJUI}),
    Role.IMPORT_APPROVER: frozenset({Capability.DASHBOARD_VIEW, Capability.ORG_UNIT_VIEW, Capability.PEGAWAI_VIEW, Capability.IMPORT_VIEW, Capability.IMPORT_APPROVE, Capability.IMPORT_APPROVE_HIGH_IMPACT}),
    Role.ACCESS_ADMIN: frozenset({Capability.DASHBOARD_VIEW, Capability.ORG_UNIT_VIEW, Capability.PEGAWAI_VIEW, Capability.ORG_UNIT_CREATE, Capability.ORG_UNIT_UPDATE, Capability.ORG_UNIT_DEACTIVATE, Capability.PEGAWAI_CREATE, Capability.PEGAWAI_UPDATE, Capability.PEGAWAI_DEACTIVATE, Capability.IDENTITY_LINK_CREATE, Capability.ACCESS_GRANT_VIEW, Capability.ACCESS_GRANT_CREATE, Capability.ACCESS_GRANT_REVOKE}),
    Role.AUDITOR: frozenset({Capability.DASHBOARD_VIEW, Capability.AUDIT_VIEW, Capability.AUDIT_EXPORT_MASKED}),
    Role.SECURITY_ADMIN: frozenset({Capability.DASHBOARD_VIEW, Capability.ORG_UNIT_VIEW, Capability.PEGAWAI_VIEW, Capability.ACCESS_GRANT_VIEW, Capability.ACCESS_GRANT_CREATE, Capability.ACCESS_GRANT_REVOKE, Capability.ACCESS_GRANT_CRITICAL_REQUEST, Capability.ACCESS_GRANT_CRITICAL_APPROVE, Capability.AUDIT_VERIFY_INTEGRITY, Capability.SECURITY_BOOTSTRAP_RECOVER}),
}

ROLE_SCOPE_RULES = {role: frozenset(ScopeType) for role in Role}
ROLE_SCOPE_RULES[Role.SECURITY_ADMIN] = frozenset({ScopeType.GLOBAL})

CRITICAL_ROLES = frozenset({Role.SECURITY_ADMIN})

if set(CAPABILITIES_BY_ROLE) != set(Role):
    raise RuntimeError("RBAC catalog must define every fixed role")
