import pytest

from idp_pegawai.consumer.cursor import CursorError, CursorSigner


@pytest.fixture
def signer():
    return CursorSigner(active_key_id="k2", keys={"k1": b"old-secret", "k2": b"new-secret"})


def claims():
    return dict(
        consumer_code="s1-internal", registration_uuid="018f0000-0000-7000-8000-000000000020",
        resource_family="pegawai", field_profile="pegawai.s1-operational.v1",
        contract_version="consumer-change.v1", query_shape="changes_v1", position=10,
    )


def test_round_trip_is_opaque_and_versioned(signer):
    token = signer.encode(**claims())
    assert token.count(".") == 1
    assert "s1-internal" not in token and "pegawai" not in token and "new-secret" not in token
    assert signer.decode(token, **{k: claims()[k] for k in ("consumer_code", "registration_uuid", "resource_family", "field_profile", "contract_version", "query_shape")})["position"] == 10


def test_tamper_and_invalid_are_rejected(signer):
    token = signer.encode(**claims())
    with pytest.raises(CursorError):
        signer.decode(token[:-1] + ("A" if token[-1] != "A" else "B"), **{k: claims()[k] for k in claims() if k != "position"})
    with pytest.raises(CursorError):
        signer.decode("not-a-cursor", **{k: claims()[k] for k in claims() if k != "position"})


def test_overlap_key_verifies_but_new_tokens_use_active(signer):
    old = CursorSigner(active_key_id="k1", keys={"k1": b"old-secret"}).encode(**claims())
    decoded = signer.decode(old, **{k: claims()[k] for k in claims() if k != "position"})
    assert decoded["position"] == 10
    assert signer.decode(signer.encode(**claims()), **{k: claims()[k] for k in claims() if k != "position"})["key_id"] == "k2"


def test_binding_mismatch_rejected(signer):
    token = signer.encode(**claims())
    with pytest.raises(CursorError):
        signer.decode(token, consumer_code="other", registration_uuid=claims()["registration_uuid"], resource_family=claims()["resource_family"], field_profile=claims()["field_profile"], contract_version=claims()["contract_version"], query_shape=claims()["query_shape"])


def test_expiry_and_position_validation(signer):
    with pytest.raises(CursorError):
        signer.encode(**{**claims(), "position": -1})
    with pytest.raises(CursorError):
        signer.encode(**{**claims(), "expires_at": "2000-01-01T00:00:00+00:00"})


def test_rejects_pii_claims(signer):
    with pytest.raises(CursorError):
        signer.encode(**{**claims(), "nip": "123"})
    with pytest.raises(CursorError):
        signer.encode(**{**claims(), "email": "a@example.com"})
