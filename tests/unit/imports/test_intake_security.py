import io
import zipfile
from pathlib import Path

import pytest

from idp_pegawai.imports.intake import IntakeError, intake_file


def xlsx_bytes(*, filename="pegawai.xlsx", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("[Content_Types].xml", "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>")
        z.writestr("xl/workbook.xml", "<workbook/>")
    return out.getvalue(), filename, content_type


def test_accepts_csv_and_stores_under_opaque_private_key(tmp_path):
    result = intake_file(io.BytesIO(b"nip,nama_lengkap\n123456789012345678,A\n"), "pegawai.csv", "text/csv", tmp_path)
    assert result.format == "csv"
    assert result.storage_key != "pegawai.csv"
    assert "/" not in result.storage_key
    assert (tmp_path / result.storage_key).read_bytes().startswith(b"nip,")
    assert result.sha256 and len(result.sha256) == 64


def test_rejects_extension_mime_or_signature_mismatch(tmp_path):
    with pytest.raises(IntakeError, match="signature"):
        intake_file(io.BytesIO(b"not an xlsx"), "pegawai.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", tmp_path)
    with pytest.raises(IntakeError, match="MIME"):
        intake_file(io.BytesIO(b"nip\n"), "pegawai.csv", "application/octet-stream", tmp_path)


def test_rejects_oversized_upload_before_storage(tmp_path):
    with pytest.raises(IntakeError, match="size"):
        intake_file(io.BytesIO(b"x" * 11), "pegawai.csv", "text/csv", tmp_path, max_size=10)
    assert not list(tmp_path.iterdir())


def test_xlsx_zip_members_stay_bounded_and_cannot_escape(tmp_path):
    data, name, mime = xlsx_bytes()
    result = intake_file(io.BytesIO(data), name, mime, tmp_path)
    assert result.format == "xlsx"
    bad = io.BytesIO()
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("../escape.txt", "x")
    with pytest.raises(IntakeError, match="ZIP"):
        intake_file(io.BytesIO(bad.getvalue()), "x.xlsx", mime, tmp_path)


def test_does_not_store_original_path_or_blob_metadata(tmp_path):
    result = intake_file(io.BytesIO(b"nip\n"), "C:\\Users\\secret\\pegawai.csv", "text/csv", tmp_path)
    assert "secret" not in result.storage_key
    assert not hasattr(result, "content")
    assert not hasattr(result, "path")


def test_filename_is_not_used_as_storage_location(tmp_path):
    result = intake_file(io.BytesIO(b"nip\n"), "../../outside.csv", "text/csv", tmp_path)
    assert result.storage_key not in ("../../outside.csv", "outside.csv")
    assert not (tmp_path.parent / "outside.csv").exists()


def test_rejects_csv_with_binary_or_empty_signature(tmp_path):
    with pytest.raises(IntakeError):
        intake_file(io.BytesIO(b""), "x.csv", "text/csv", tmp_path)
    with pytest.raises(IntakeError):
        intake_file(io.BytesIO(b"\x00\x01bad"), "x.csv", "text/csv", tmp_path)


def test_xlsx_zip_compression_ratio_is_bounded(tmp_path):
    raw = b"A" * 10000
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml", raw)
    with pytest.raises(IntakeError, match="ZIP"):
        intake_file(io.BytesIO(out.getvalue()), "x.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", tmp_path, max_uncompressed_size=100)
