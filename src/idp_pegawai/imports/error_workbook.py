"""Safe, self-contained error-workbook artifact for the pegawai retry loop."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape as xml_escape

PROFILE = "pegawai_error_retry_v1"
HEADERS = ("nip", "nama_lengkap", "email_dinas", "email_google", "org_unit_code", "status_pegawai")
SHEETS = ("instructions", "summary", "pegawai", "diagnostics", "reference_status", "reference_org_units", "metadata")


def escape_formula(value: Any) -> Any:
    """Escape spreadsheet-leading formula characters for display only."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@dataclass(frozen=True)
class ErrorWorkbookArtifact:
    profile: str
    sheets: dict[str, list[dict[str, Any]]]
    display_sheets: dict[str, list[dict[str, Any]]]
    metadata: dict[str, Any]
    content: bytes


def _cell(value: Any) -> str:
    if value is None:
        return "<c t=\"inlineStr\"><is><t/></is></c>"
    text = xml_escape(str(value), {"\n": "&#10;", "\r": "&#13;", "\t": "&#9;"})
    return f'<c t="inlineStr"><is><t>{text}</t></is></c>'


def _sheet(rows: list[list[Any]]) -> bytes:
    body = "".join(f'<row r="{i}">{"".join(_cell(v) for v in row)}</row>' for i, row in enumerate(rows, 1))
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{body}</sheetData></worksheet>').encode()


def build_error_workbook(rows, validation, *, parent_batch_uuid, root_batch_uuid) -> ErrorWorkbookArtifact:
    """Build all-row retry data while retaining canonical values separately from display values."""
    canonical = [{h: row.get(h) for h in HEADERS} for row in rows if any(row.get(h) not in (None, "") for h in HEADERS)]
    display = [{h: escape_formula(row[h]) for h in HEADERS} for row in canonical]
    issues = getattr(validation, "issues", [])
    diagnostics = [{"code": i.code, "severity": i.severity, "row_number": i.row_number, "field": i.field, "message": i.message} for i in issues]
    metadata = {"profile": PROFILE, "version": "1", "parent_batch_uuid": str(parent_batch_uuid), "root_batch_uuid": str(root_batch_uuid), "retry_lineage_token": uuid4().hex, "created_at": datetime.now(timezone.utc).isoformat()}
    sheets = {"instructions": [{"text": "Perbaiki data pada sheet pegawai lalu upload kembali."}], "summary": [{"retry_data_rows": len(canonical), "error_diagnostics": sum(i.severity in {"error", "fatal"} for i in issues), "warning_diagnostics": sum(i.severity == "warning" for i in issues)}], "pegawai": canonical, "diagnostics": diagnostics, "reference_status": [{"status": s} for s in ("aktif", "mutasi_keluar", "pensiun", "nonaktif", "meninggal")], "reference_org_units": [], "metadata": [metadata]}
    display_sheets = dict(sheets)
    display_sheets["pegawai"] = display
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>')
        z.writestr("xl/workbook.xml", '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets>' + ''.join(f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(SHEETS, 1)) + '</sheets></workbook>')
        for i, name in enumerate(SHEETS, 1):
            data = display_sheets[name]
            vals = [list(data[0]) if data else ["value"]] + [list(r.values()) for r in data]
            z.writestr(f"xl/worksheets/sheet{i}.xml", _sheet(vals))
    return ErrorWorkbookArtifact(PROFILE, sheets, display_sheets, metadata, stream.getvalue())


__all__ = ["ErrorWorkbookArtifact", "build_error_workbook", "escape_formula"]
