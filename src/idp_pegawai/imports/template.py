"""Detection of the explicitly supported canonical input template."""
from dataclasses import dataclass
import re

class TemplateError(ValueError):
    pass

@dataclass(frozen=True)
class Template:
    version: str
    headers: dict[str, str]

ALIASES = {
    "nip": {"nip", "nomor induk pegawai", "nomor_induk_pegawai"},
    "full_name": {"full name", "nama lengkap", "nama", "full_name"},
    "birth_date": {"birth date", "tanggal lahir", "tgl lahir", "birth_date"},
    "joined_at": {"joined at", "tanggal masuk", "joined_at"},
    "active": {"active", "aktif", "is active", "is_active"},
    "score": {"score", "nilai"},
    "serial_date": {"serial date", "tanggal serial", "serial_date"},
}

def _key(value):
    return re.sub(r"[\s-]+", "_", str(value).strip().lower())

def detect_template(headers):
    found = {}
    for header in headers:
        normalized = _key(header)
        matches = [field for field, aliases in ALIASES.items() if normalized in {_key(a) for a in aliases}]
        if not matches:
            raise TemplateError(f"unknown header/template column: {header}")
        if matches[0] in found:
            raise TemplateError(f"duplicate template column: {header}")
        found[matches[0]] = header
    required = {"nip", "full_name"}
    missing = required - found.keys()
    if missing:
        raise TemplateError(f"template missing required headers: {', '.join(sorted(missing))}")
    return Template("canonical-input-v1", found)

def canonical_headers():
    return dict(ALIASES)
