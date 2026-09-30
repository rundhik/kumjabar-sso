import datetime as dt
import math
from .mapping import AuditValue

class ParseError(ValueError):
    pass

_DATE_FIELDS = {"birth_date", "serial_date"}
_DATETIME_FIELDS = {"joined_at"}
_BOOL_FIELDS = {"active"}
_NUMBER_FIELDS = {"score"}

def _date(value, field):
    if isinstance(value, (dt.date, dt.datetime)):
        return value.date() if isinstance(value, dt.datetime) else value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(value))
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try: return dt.datetime.strptime(text, fmt).date()
        except ValueError: pass
    raise ParseError(f"{field}: invalid date/datetime value {value!r}")

def _datetime(value, field):
    if isinstance(value, dt.datetime): return value
    if isinstance(value, dt.date): return dt.datetime.combine(value, dt.time())
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try: return dt.datetime.strptime(text, fmt)
        except ValueError: pass
    raise ParseError(f"{field}: invalid date/datetime value {value!r}")

def _number(value, field):
    if isinstance(value, (int, float)) and not isinstance(value, bool): return value
    text = str(value).strip().replace(".", "").replace(",", ".")
    try: return float(text) if "." in text else int(text)
    except ValueError: raise ParseError(f"{field}: invalid numeric value {value!r}")

def _bool(value, field):
    if isinstance(value, bool): return value
    if isinstance(value, (int, float)) and value in (0, 1): return bool(value)
    text = str(value).strip().lower()
    if text in {"ya", "yes", "true", "1", "aktif"}: return True
    if text in {"tidak", "no", "false", "0", "nonaktif"}: return False
    raise ParseError(f"{field}: invalid boolean value {value!r}")

def normalize_row(row):
    result = {}
    for field, item in row.items():
        raw = item.raw if isinstance(item, AuditValue) else item
        try:
            normalized = (_date(raw, field) if field in _DATE_FIELDS else _datetime(raw, field) if field in _DATETIME_FIELDS else _bool(raw, field) if field in _BOOL_FIELDS else _number(raw, field) if field in _NUMBER_FIELDS else raw)
        except ParseError: raise
        result[field] = AuditValue(raw, item.mapped if isinstance(item, AuditValue) else raw, normalized)
    return result
