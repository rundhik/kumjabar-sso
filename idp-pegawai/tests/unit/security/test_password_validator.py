"""Unit tests — password validator Slice 1 (RED→GREEN).

Kontrak Dok 37 §5: 12 char, 4 kategori, username/email substring, triple repeat, sequence.
Pesan error bahasa Indonesia.
"""
import pytest

from idp_pegawai.security.password import validate_password_strength


class TestPasswordValidatorSuccess:
    def test_strong_password_lolos(self):
        assert validate_password_strength("Str0ng!Pass#12") == []

    def test_strong_alt_lolos(self):
        # 12+ tanpa sequence/triple
        assert validate_password_strength("V4l!d#Qm9z$Kp1") == []

    def test_exactly_12_lolos_jika_kuat(self):
        # Pastikan 12 char bisa lolos bila 4 kategori tanpa sequence/triple
        # Hindari sequence abc/123
        assert validate_password_strength("A1b!C2d#E3f$") == []


class TestPasswordValidatorLength:
    def test_kurang_dari_12_gagal(self):
        errs = validate_password_strength("Admin123!ab")
        assert any("12" in e for e in errs)

    def test_lebih_dari_128_gagal(self):
        long_pwd = "A1b!" + "x" * 130
        errs = validate_password_strength(long_pwd)
        assert any("128" in e for e in errs)


class TestPasswordValidatorKategori:
    def test_tanpa_upper_gagal(self):
        errs = validate_password_strength("str0ng!pass#12")
        assert any("besar" in e.lower() for e in errs)

    def test_tanpa_lower_gagal(self):
        errs = validate_password_strength("STR0NG!PASS#12")
        assert any("kecil" in e.lower() for e in errs)

    def test_tanpa_digit_gagal(self):
        errs = validate_password_strength("Strong!Pass#ab")
        assert any("angka" in e.lower() for e in errs)

    def test_tanpa_symbol_gagal(self):
        errs = validate_password_strength("StrongPass1234")
        assert any("simbol" in e.lower() for e in errs)

    def test_password123_gagal_multi(self):
        errs = validate_password_strength("password123")
        assert len(errs) >= 2  # <12? actually 11 + no upper + no symbol + sequence
        # password123 = 11 chars, no upper, no symbol, sequence 123
        assert any("12" in e for e in errs)


class TestPasswordValidatorUsernameEmail:
    def test_mengandung_username_gagal(self):
        errs = validate_password_strength("Admin123!@#xyz", username="admin")
        assert any("username" in e.lower() for e in errs)

    def test_mengandung_username_substring_gagal(self):
        # potongan >=3 char dari username
        errs = validate_password_strength("MyAdm!Pass#12X", username="admin")
        assert any("username" in e.lower() for e in errs)

    def test_mengandung_email_local_gagal(self):
        errs = validate_password_strength("Budi!Pass#12XX", email="budi@jabarprov.go.id")
        assert any("email" in e.lower() for e in errs)

    def test_case_insensitive_username(self):
        errs = validate_password_strength("ADMIN!Pass#12X", username="admin")
        assert any("username" in e.lower() for e in errs)


class TestPasswordValidatorTripleRepeat:
    def test_aaa_triple_gagal(self):
        errs = validate_password_strength("AAAbbb123!!!")
        # harus ada triple repeat error (AAA) + sequence (123)
        assert any("berulang" in e.lower() or "aaa" in e.lower() or "3 karakter" in e.lower() for e in errs)

    def test_triple_111_gagal(self):
        errs = validate_password_strength("Abc!111Def#12")
        assert any("berulang" in e.lower() for e in errs)


class TestPasswordValidatorSequence:
    def test_abc_sequence_gagal(self):
        errs = validate_password_strength("Abc!Xyz#123Qw")
        assert any("urutan" in e.lower() for e in errs)

    def test_qwerty_gagal(self):
        errs = validate_password_strength("Qwerty123!@#A")
        assert any("urutan" in e.lower() for e in errs)

    def test_123_sequence_gagal(self):
        errs = validate_password_strength("MyPass123!@#Ab")
        assert any("urutan" in e.lower() for e in errs)


class TestPasswordValidatorMessagesBahasaIndonesia:
    def test_pesan_bahasa_indonesia(self):
        errs = validate_password_strength("short")
        assert errs  # ada error
        # minimal satu pesan mengandung kata Indonesia
        assert any("Password" in e for e in errs)
