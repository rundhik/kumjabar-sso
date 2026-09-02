import pytest

from idp_pegawai.imports.mapping import map_row, MappingError
from idp_pegawai.imports.template import detect_template, TemplateError


def test_detects_canonical_v1_from_headers_and_maps_aliases():
    headers = ["NIP", "Nama Lengkap", "Tanggal Lahir", "Aktif"]
    template = detect_template(headers)
    assert template.version == "canonical-input-v1"
    result = map_row({"NIP": "123", "Nama Lengkap": "Siti", "Tanggal Lahir": "01/02/1990", "Aktif": "Ya"}, template)
    assert result["nip"].raw == "123"
    assert result["full_name"].mapped == "Siti"
    assert result["active"].mapped == "Ya"


def test_unknown_or_missing_header_is_explicit():
    with pytest.raises(TemplateError, match="template"):
        detect_template(["NIP", "Kolom Aneh"])
    template = detect_template(["nip", "full_name", "active"])
    with pytest.raises(MappingError, match="active"):
        map_row({"nip": "1", "full_name": "A"}, template)
