import pytest

from idp_pegawai.integrations.oidc.claims import claims_for, filter_claims


GLOBAL = {"iss", "sub", "aud", "azp", "exp", "nbf", "iat"}


def test_fixed_profiles_expose_only_minimum_claims():
    assert claims_for("portal-minimal.v1") == GLOBAL | {"user_type", "pegawai_uuid"}
    assert claims_for("s1-minimal.v1") == GLOBAL | {"user_type", "pegawai_uuid"}


@pytest.mark.parametrize("profile", ["portal-minimal.v1", "s1-minimal.v1"])
def test_arbitrary_claims_are_rejected(profile):
    with pytest.raises(ValueError):
        filter_claims(profile, {"sub": "s", "custom": "not-approved"})


@pytest.mark.parametrize("forbidden", ["NIP", "nip", "email", "org_tree", "jabatan", "grants", "cursor"])
def test_sensitive_or_non_oidc_claims_are_not_catalogued(forbidden):
    assert all(forbidden != claim for claims in (claims_for("portal-minimal.v1"), claims_for("s1-minimal.v1")) for claim in claims)


def test_filter_returns_catalogued_claims_and_rejects_unknown_keys():
    values = {claim: claim for claim in claims_for("portal-minimal.v1")}
    assert filter_claims("portal-minimal.v1", values) == values
    with pytest.raises(ValueError):
        filter_claims("portal-minimal.v1", {"sub": "s", "cursor": "opaque"})


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError):
        claims_for("anything.v1")


def test_minimum_claims_cannot_be_omitted():
    values = {"sub": "s"}
    with pytest.raises(ValueError):
        filter_claims("portal-minimal.v1", values)
