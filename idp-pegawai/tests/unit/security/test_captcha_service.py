"""Unit — captcha service Slice 2 (RED→GREEN). Selalu tampil, Redis TTL 5m, sekali pakai.

Pakai dict sebagai redis fake agar tidak butuh fakeredis (image base tidak punya).
Dict memenuhi get/setex/delete ala captcha service fallback.
"""
import base64
import uuid

import pytest

from idp_pegawai.security.captcha import _clear_fallback_store, generate_captcha, verify_captcha

# Helper: redis dict-like minimal yang dipakai service
class FakeRedis(dict):
    def setex(self, key, ttl, value):
        self[key] = value
    def get(self, key, default=None):
        return super().get(key, default)
    def delete(self, key):
        self.pop(key, None)


class TestCaptchaGenerate:
    def setup_method(self):
        _clear_fallback_store()

    def test_generate_returns_id_and_base64(self):
        fake = FakeRedis()
        result = generate_captcha(redis_client=fake)
        assert "captcha_id" in result
        assert "image_base64" in result
        uuid.UUID(result["captcha_id"])
        assert result["image_base64"].startswith("data:image/png;base64,")
        b64 = result["image_base64"].split(",", 1)[1]
        raw = base64.b64decode(b64)
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"
        stored = fake.get(f"captcha:{result['captcha_id']}")
        assert stored is not None
        assert len(stored) == 5

    def test_generate_custom_length(self):
        fake = FakeRedis()
        result = generate_captcha(redis_client=fake, length=6)
        assert len(fake.get(f"captcha:{result['captcha_id']}")) == 6


class TestCaptchaVerify:
    def setup_method(self):
        _clear_fallback_store()

    def test_verify_correct_case_insensitive_and_single_use(self):
        fake = FakeRedis()
        result = generate_captcha(redis_client=fake)
        stored = fake.get(f"captcha:{result['captcha_id']}")
        assert verify_captcha(result["captcha_id"], stored.upper(), redis_client=fake) is True
        assert fake.get(f"captcha:{result['captcha_id']}") is None
        assert verify_captcha(result["captcha_id"], stored, redis_client=fake) is False

    def test_verify_wrong_answer_false_and_consumed(self):
        fake = FakeRedis()
        result = generate_captcha(redis_client=fake)
        cid = result["captcha_id"]
        assert verify_captcha(cid, "XXXXX", redis_client=fake) is False
        assert fake.get(f"captcha:{cid}") is None

    def test_verify_expired_or_missing_false(self):
        fake = FakeRedis()
        assert verify_captcha(str(uuid.uuid4()), "abcde", redis_client=fake) is False
        assert verify_captcha("", "abcde", redis_client=fake) is False
        assert verify_captcha(str(uuid.uuid4()), "", redis_client=fake) is False

    def test_fallback_store_without_redis(self):
        _clear_fallback_store()
        result = generate_captcha(redis_client=None)
        # fallback harus terisi bila tanpa redis client, tapi kita pakai fallback_store
        # generate_captcha tanpa redis pakai _fallback_store — verify juga via fallback
        # ambil key fallback
        from idp_pegawai.security.captcha import _fallback_store as store

        key = f"captcha:{result['captcha_id']}"
        assert key in store
        stored = store[key]
        assert verify_captcha(result["captcha_id"], stored, redis_client=None) is True
        assert key not in store
