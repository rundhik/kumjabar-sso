import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from idp_pegawai.integrations.oidc.validator import OIDCValidationError, validate_token

ISSUER = "https://sso.example/realms/kumjabar"
AUDIENCE = "aud:idp-consumer-feed"
AZP = "portal-feed"


@pytest.fixture
def oidc_token_fixture():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key()
    now = int(time.time())
    claims = {"iss": ISSUER, "sub": "subject-1", "aud": AUDIENCE, "azp": AZP,
              "exp": now + 300, "nbf": now - 1, "iat": now}
    token = jwt.encode(claims, private, algorithm="RS256", headers={"kid": "fake-1"})
    return token, {"fake-1": public}, claims, private, now


def test_valid_rs256_token_from_fake_jwks_is_accepted(oidc_token_fixture):
    token, jwks, _, _, now = oidc_token_fixture
    assert validate_token(token, issuer=ISSUER, audience=AUDIENCE, azp=AZP, jwks=jwks, now=now)["sub"] == "subject-1"


@pytest.mark.parametrize("change", [
    {"iss": "https://wrong"}, {"aud": "wrong"}, {"azp": "wrong"},
    {"exp": -1}, {"nbf": 9999999999}, {"iat": 9999999999},
])
def test_wrong_claim_token_is_rejected(oidc_token_fixture, change):
    _, jwks, claims, private, now = oidc_token_fixture
    bad = {**claims, **change}
    token = jwt.encode(bad, private, algorithm="RS256", headers={"kid": "fake-1"})
    with pytest.raises(OIDCValidationError):
        validate_token(token, issuer=ISSUER, audience=AUDIENCE, azp=AZP, jwks=jwks, now=now)


def test_wrong_signature_and_algorithm_are_rejected(oidc_token_fixture):
    _, jwks, claims, _, now = oidc_token_fixture
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(claims, other, algorithm="RS256", headers={"kid": "fake-1"})
    with pytest.raises(OIDCValidationError):
        validate_token(token, issuer=ISSUER, audience=AUDIENCE, azp=AZP, jwks=jwks, now=now)
    token = jwt.encode(claims, "not-a-key", algorithm="HS256", headers={"kid": "fake-1"})
    with pytest.raises(OIDCValidationError):
        validate_token(token, issuer=ISSUER, audience=AUDIENCE, azp=AZP, jwks=jwks, now=now)


def test_required_time_claims_are_enforced(oidc_token_fixture):
    _, jwks, claims, private, now = oidc_token_fixture
    for name in ("exp", "nbf", "iat"):
        bad = {k: v for k, v in claims.items() if k != name}
        token = jwt.encode(bad, private, algorithm="RS256", headers={"kid": "fake-1"})
        with pytest.raises(OIDCValidationError):
            validate_token(token, issuer=ISSUER, audience=AUDIENCE, azp=AZP, jwks=jwks, now=now)
