"""Pure, fail-closed validation for normalized import rows."""
from dataclasses import dataclass, field
import re
from typing import Any, Iterable

STATUSES = {"aktif", "mutasi_keluar", "pensiun", "nonaktif", "meninggal"}
FORBIDDEN_FIELDS = {"jabatan", "jabatan_type", "jenis_jabatan", "nama_jabatan", "label_jabatan", "plt", "plh", "histori_jabatan", "sk_jabatan", "role", "permission", "provider_subject", "email_verified", "keycloak_user_id"}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str
    row_number: int | None = None
    field: str | None = None
    message: str = ""
    CODES = frozenset({"nip_required", "nip_format_invalid", "duplicate_nip_in_file", "nama_lengkap_required", "status_pegawai_required", "status_pegawai_invalid", "active_pegawai_requires_org_unit", "inactive_status_with_active_eligibility", "org_unit_code_not_found", "email_format_invalid", "duplicate_email_in_file", "active_pegawai_without_email", "forbidden_header", "formula_injection_detected", "text_too_long", "control_character_not_allowed"})

@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)
    @property
    def blocking(self): return any(i.severity in {"error", "fatal"} for i in self.issues)
    @property
    def valid(self): return not self.blocking


def _value(v):
    return getattr(v, "normalized", v)

def validate_rows(rows: Iterable[dict[str, Any]], org_codes: Iterable[str], headers=None) -> ValidationResult:
    result, rows = ValidationResult(), list(rows)
    if headers:
        for h in headers:
            if str(h).strip().lower() in FORBIDDEN_FIELDS:
                result.issues.append(ValidationIssue("forbidden_header", "fatal", field=str(h), message="Kolom dikelola di sistem lain."))
    nips = [_value(r.get("nip")) for r in rows]
    emails = [_value(r.get(k)) for r in rows for k in ("email_dinas", "email_google") if _value(r.get(k))]
    for idx, row in enumerate(rows, 1):
        def add(code, severity="error", field=None): result.issues.append(ValidationIssue(code, severity, idx, field))
        nip = _value(row.get("nip"))
        if not nip: add("nip_required", field="nip")
        elif not isinstance(nip, str) or not re.fullmatch(r"[0-9]{18}", nip, re.ASCII): add("nip_format_invalid", field="nip")
        if nip and nips.count(nip) > 1: add("duplicate_nip_in_file", field="nip")
        if not _value(row.get("nama_lengkap")): add("nama_lengkap_required", field="nama_lengkap")
        status = _value(row.get("status_pegawai"))
        if not status: add("status_pegawai_required", field="status_pegawai")
        elif status not in STATUSES: add("status_pegawai_invalid", field="status_pegawai")
        if status == "aktif" and not _value(row.get("org_unit_code")): add("active_pegawai_requires_org_unit", field="org_unit_code")
        if "is_active" in row and bool(_value(row["is_active"])) != (status == "aktif"): add("inactive_status_with_active_eligibility", field="is_active")
        org = _value(row.get("org_unit_code"))
        if org and org not in set(org_codes): add("org_unit_code_not_found", field="org_unit_code")
        for f in ("email_dinas", "email_google"):
            email = _value(row.get(f))
            if email:
                if not EMAIL_RE.fullmatch(str(email)): add("email_format_invalid", field=f)
                if emails.count(email) > 1: add("duplicate_email_in_file", field=f)
        if status == "aktif" and not any(_value(row.get(f)) for f in ("email_dinas", "email_google")): add("active_pegawai_without_email", "warning", "email_dinas")
        for f, v in row.items():
            if isinstance(_value(v), str) and (_value(v).startswith(("=", "+", "-", "@"))): add("formula_injection_detected", field=f)
            if isinstance(_value(v), str) and len(_value(v)) > 255: add("text_too_long", field=f)
            if isinstance(_value(v), str) and any(ord(c) < 32 and c not in "\t\n\r" for c in _value(v)): add("control_character_not_allowed", field=f)
    return result

__all__ = ["ValidationIssue", "ValidationResult", "validate_rows"]
