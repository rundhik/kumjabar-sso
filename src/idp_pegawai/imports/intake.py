from __future__ import annotations

import hashlib
import io
import secrets
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


class IntakeError(ValueError):
    pass


@dataclass(frozen=True)
class IntakeResult:
    format: str
    storage_key: str
    sha256: str
    size: int
    original_filename: str
    mime_type: str


CSV_MIMES = {"text/csv", "application/csv", "text/plain"}
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _read(stream: BinaryIO, limit: int) -> bytes:
    data = stream.read(limit + 1)
    if len(data) > limit:
        raise IntakeError("upload melebihi batas size")
    return data


def _check_xlsx(data: bytes, max_uncompressed_size: int) -> None:
    if not data.startswith(b"PK\x03\x04"):
        raise IntakeError("signature XLSX tidak valid")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if archive.testzip() is not None:
                raise IntakeError("ZIP XLSX rusak")
            names = [item.filename for item in archive.infolist()]
            if "xl/workbook.xml" not in names or "[Content_Types].xml" not in names:
                raise IntakeError("struktur ZIP XLSX tidak valid")
            total = 0
            for item in archive.infolist():
                if item.filename.startswith(("/", "\\")) or ".." in Path(item.filename).parts:
                    raise IntakeError("ZIP path boundary tidak aman")
                total += item.file_size
                if total > max_uncompressed_size:
                    raise IntakeError("ZIP XLSX melebihi batas size")
    except zipfile.BadZipFile as exc:
        raise IntakeError("ZIP XLSX tidak valid") from exc


def intake_file(stream: BinaryIO, original_filename: str, mime_type: str, storage_dir: Path, *, max_size: int = 10 * 1024 * 1024, max_uncompressed_size: int = 50 * 1024 * 1024) -> IntakeResult:
    suffix = Path(original_filename).suffix.lower()
    if suffix == ".csv":
        if mime_type not in CSV_MIMES:
            raise IntakeError("MIME tidak diizinkan untuk CSV")
        kind = "csv"
    elif suffix == ".xlsx":
        if mime_type != XLSX_MIME:
            raise IntakeError("MIME tidak diizinkan untuk XLSX")
        kind = "xlsx"
    else:
        raise IntakeError("ekstensi file tidak diizinkan")
    data = _read(stream, max_size)
    if not data or (kind == "csv" and b"\x00" in data):
        raise IntakeError("signature file tidak valid")
    if kind == "xlsx":
        _check_xlsx(data, max_uncompressed_size)
    key = secrets.token_urlsafe(32)
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / key).write_bytes(data)
    return IntakeResult(kind, key, hashlib.sha256(data).hexdigest(), len(data), Path(original_filename).name, mime_type)

__all__ = ["IntakeError", "IntakeResult", "intake_file"]
