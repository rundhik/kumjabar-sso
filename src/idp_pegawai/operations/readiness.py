"""Static staging-readiness checks; never performs deployment or network activation."""
from __future__ import annotations


def review_compose(compose: dict) -> list[str]:
    findings: list[str] = []
    services = compose.get("services", {})
    kc = services.get("kumjabar_keycloak", {})
    image = kc.get("image", "")
    if image.endswith(":latest") or ":" not in image:
        findings.append("BLOCKER: Keycloak image belum exact-pinned (menggunakan latest/tanpa tag)")
    command = " ".join(map(str, kc.get("command", [])))
    if "start-dev" in command or kc.get("environment", {}).get("KC_HTTP_ENABLED") == "true":
        findings.append("BLOCKER: Keycloak masih dev/HTTP; staging wajib HTTPS")
    return findings


def review_gateway(routes: dict, security: dict) -> list[str]:
    findings: list[str] = []
    private = routes.get("private_ingress", {})
    if private.get("authentication") != "service_jwt" or not private.get("required_scope"):
        findings.append("BLOCKER: private gateway route belum mewajibkan service authentication/scope")
    tls = security.get("tls", {})
    if tls.get("verify_peer", tls.get("verify_upstream")) is not True:
        findings.append("BLOCKER: TLS peer verification gateway belum wajib")
    if any(p in routes.get("public_ingress", {}).get("allow", []) for p in ("/idp-pegawai/internal/*", "/idp-pegawai/feed/*")):
        findings.append("BLOCKER: private route terbuka pada public ingress")
    return findings


def review_oidc(contract: dict) -> list[str]:
    required = {"jwks", "pkce", "state", "nonce"}
    missing = sorted(required - set(contract))
    return [f"BLOCKER: OIDC contract missing {name}" for name in missing]
