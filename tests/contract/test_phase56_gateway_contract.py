from pathlib import Path
import yaml

ROOT = Path(__file__).parents[2]

def load(name):
    return yaml.safe_load((ROOT / name).read_text())

def test_public_ingress_excludes_private_routes():
    routes = load("deploy/gateway/routes.yaml")
    public = routes["public_ingress"]["allow"]
    assert not any("/internal" in x or "/feed" in x or "/worker" in x for x in public)
    assert set(routes["public_ingress"]["deny_prefixes"]) >= {"/idp-pegawai/internal/", "/idp-pegawai/feed/", "/idp-pegawai/worker/"}

def test_gateway_security_bounds_and_explicit_proxy():
    s = load("deploy/gateway/security-baseline.yaml")
    assert s["trusted_proxy"]["enabled"] is True
    assert s["trusted_proxy"]["source"] == "explicit_allowlist"
    assert s["tls"]["verify_upstream"] is True
    assert s["limits"]["max_body_bytes"] > 0
    assert s["limits"]["max_header_bytes"] > 0
    assert s["limits"]["rate_limit_per_minute"] > 0
    assert all(value > 0 for value in s["limits"]["timeout_seconds"].values())
    assert s["mutation_retry"]["enabled"] is False

def test_logging_redaction_is_complete():
    fields = set(load("deploy/gateway/security-baseline.yaml")["logging"]["redact_fields"])
    assert {"pii", "token", "cursor", "payload"} <= fields
