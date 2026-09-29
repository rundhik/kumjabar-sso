import datetime as dt
import pytest

from idp_pegawai.imports.normalization import normalize_row, ParseError


def test_normalizes_dates_serial_numbers_and_booleans_with_audit_values():
    row = {
        "birth_date": "31/12/1990", "joined_at": "2024-01-02 03:04:05",
        "score": "1.250,50", "active": "Ya", "serial_date": 45292,
    }
    result = normalize_row(row)
    assert result["birth_date"].normalized == dt.date(1990, 12, 31)
    assert result["joined_at"].normalized == dt.datetime(2024, 1, 2, 3, 4, 5)
    assert result["score"].normalized == 1250.50
    assert result["active"].normalized is True
    assert result["serial_date"].normalized == dt.date(2024, 1, 1)
    assert result["birth_date"].raw == "31/12/1990"


def test_parse_failures_are_explicit():
    with pytest.raises(ParseError, match="birth_date"):
        normalize_row({"birth_date": "not-a-date"})
    with pytest.raises(ParseError, match="active"):
        normalize_row({"active": "maybe"})
