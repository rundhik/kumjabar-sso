from pathlib import Path

import yaml

from idp_pegawai.operations.readiness import review_gateway


def _find_contract():
    for p in Path(__file__).resolve().parents:
        cand = p / "docs/contracts/gateway-private-route.synthetic.yml"
        if cand.exists():
            return cand
        cand2 = p / "idp-pegawai/docs/contracts/gateway-private-route.synthetic.yml"
        if cand2.exists():
            return cand2
    return Path(__file__).parents[3] / "docs/contracts/gateway-private-route.synthetic.yml"


CONTRACT = _find_contract()


def test_private_gateway_contract_is_not_public_and_requires_service_jwt():
    contract = yaml.safe_load(CONTRACT.read_text())
    assert "/idp-pegawai/internal/*" not in contract["public_ingress"]["allow"]
    assert "/idp-pegawai/feed/*" not in contract["public_ingress"]["allow"]
    private = contract["private_ingress"]
    assert private["authentication"] == "service_jwt"
    assert private["audience"] == "idp-pegawai-internal"
    assert private["required_scope"] == "feed:read"
    assert contract["security"]["tls"]["verify_upstream"] is True


def test_gateway_readiness_review_accepts_synthetic_contract():
    contract = yaml.safe_load(CONTRACT.read_text())
    routes = {
        "public_ingress": contract["public_ingress"],
        "private_ingress": contract["private_ingress"],
    }
    assert review_gateway(routes, contract["security"]) == []


def test_private_route_contract_records_deny_matrix():
    contract = yaml.safe_load(CONTRACT.read_text())
    assert contract["responses"] == {
        "anonymous": 401,
        "missing_scope": 403,
        "invalid_audience": 403,
        "valid_service_token": 200,
    }
