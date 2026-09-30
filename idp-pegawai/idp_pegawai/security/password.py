"""Password strength validator — kontrak beku Dok 37 §5.

Aturan BEKU:
1. min 12, max 128
2. wajib ada: uppercase + lowercase + digit + symbol
3. tidak boleh mengandung username/email (case-insensitive, potongan >=3)
4. tidak boleh 3 char berurutan sama (aaa, 111) atau sequence (abc, 123, qwerty potongan)
5. pesan error selalu bahasa Indonesia
"""
from __future__ import annotations

import re
import string

# Simbol yang dihitung sebagai kategori symbol
_SYMBOLS = set(string.punctuation)

# Sequence keyboard/QWERTY + alphabet + numeric untuk deteksi potongan >=3
_KEYBOARD_SEQUENCES = [
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
    "qwerty",
    "abcdefghijklmnopqrstuvwxyz",
    "0123456789",
]

_TRIPLE_RE = re.compile(r"(.)\1\1")


def _contains_forbidden_substring(password_lower: str, source: str) -> bool:
    """True jika password mengandung source atau potongan >=3 dari source (case-insensitive)."""
    src = source.strip().lower()
    if len(src) < 3:
        return False
    pwd = password_lower
    # whole source
    if src in pwd:
        return True
    # any substring >=3 (sliding window minimal 3)
    # Untuk performa, cukup cek substring panjang 3..len(src) yang muncul di password
    # Ambil semua potongan 3 dari src, cek di pwd; jika src panjang, potongan 3 sudah cukup sinyal.
    # Dok menyebut "potongan >=3 char" — deteksi 3-char sudah memenuhi.
    for i in range(len(src) - 2):
        sub = src[i : i + 3]
        if len(sub) >= 3 and sub in pwd:
            return True
        # juga cek potongan lebih panjang (mis. 4) untuk hindari false positive pendek yang umum
        # tapi 3-char sudah cukup strict sesuai kontrak
    return False


def _has_sequential_chars(password: str) -> bool:
    pwd_lower = password.lower()
    # 1) keyboard/qwerty substrings
    for seq in _KEYBOARD_SEQUENCES:
        seq_l = seq.lower()
        for i in range(len(seq_l) - 2):
            sub = seq_l[i : i + 3]
            if sub in pwd_lower:
                return True
            # juga cek reverse
            if sub[::-1] in pwd_lower:
                return True
    # 2) generic ordinal sequence asc/desc 3 chars (abc, cba, 123, 321)
    for i in range(len(password) - 2):
        a, b, c = password[i], password[i + 1], password[i + 2]
        # hanya cek alnum sequences agar tidak false positive pada simbol acak
        if a.isalnum() and b.isalnum() and c.isalnum():
            oa, ob, oc = ord(a.lower()), ord(b.lower()), ord(c.lower())
            if (ob == oa + 1 and oc == ob + 1) or (ob == oa - 1 and oc == ob - 1):
                return True
    return False


def validate_password_strength(password: str, username: str = "", email: str = "") -> list[str]:
    """Return [] jika kuat, atau list pesan error bahasa Indonesia."""
    errors: list[str] = []

    if password is None:
        password = ""
    if not isinstance(password, str):
        password = str(password)

    pwd = password
    pwd_lower = pwd.lower()

    # 1. panjang
    if len(pwd) < 12:
        errors.append("Password minimal 12 karakter")
    if len(pwd) > 128:
        errors.append("Password maksimal 128 karakter")

    # 2. kategori
    if not re.search(r"[A-Z]", pwd):
        errors.append("Password wajib mengandung huruf besar (A-Z)")
    if not re.search(r"[a-z]", pwd):
        errors.append("Password wajib mengandung huruf kecil (a-z)")
    if not re.search(r"[0-9]", pwd):
        errors.append("Password wajib mengandung angka (0-9)")
    if not any(ch in _SYMBOLS for ch in pwd):
        errors.append("Password wajib mengandung simbol (mis. !@#$%)")

    # 3. username/email
    if username and isinstance(username, str) and username.strip():
        if _contains_forbidden_substring(pwd_lower, username):
            errors.append("Password tidak boleh mengandung username")
    if email and isinstance(email, str) and email.strip():
        email_l = email.strip().lower()
        # cek local part dan full email
        local = email_l.split("@")[0] if "@" in email_l else email_l
        # cek local part
        if _contains_forbidden_substring(pwd_lower, local):
            errors.append("Password tidak boleh mengandung email")
        elif _contains_forbidden_substring(pwd_lower, email_l):
            # hanya jika belum ketemu via local, cek full email (hindari duplikat pesan)
            errors.append("Password tidak boleh mengandung email")
        else:
            # cek token split email by non-alnum (mis. domain)
            tokens = re.split(r"[^a-z0-9]+", email_l)
            for tok in tokens:
                if len(tok) >= 3 and tok in pwd_lower:
                    errors.append("Password tidak boleh mengandung email")
                    break

    # 4. triple repeat
    if _TRIPLE_RE.search(pwd):
        errors.append("Password tidak boleh mengandung 3 karakter berulang berurutan (mis. aaa atau 111)")

    # 5. sequence
    if _has_sequential_chars(pwd):
        errors.append("Password tidak boleh mengandung urutan karakter berurutan (mis. abc atau 123)")

    return errors


__all__ = ["validate_password_strength"]
