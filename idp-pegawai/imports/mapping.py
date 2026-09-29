from dataclasses import dataclass
from .template import Template

class MappingError(ValueError):
    pass

@dataclass(frozen=True)
class AuditValue:
    raw: object
    mapped: object
    normalized: object = None

def map_row(row, template):
    result = {}
    for field, header in template.headers.items():
        if header not in row:
            raise MappingError(f"missing mapped field: {field}")
        result[field] = AuditValue(raw=row[header], mapped=row[header])
    return result
