import json
from idp_pegawai.integrations.keycloak.policy import KeycloakEndpointPolicy
from idp_pegawai.integrations.keycloak.transport import KeycloakHTTPTransport

class Response:
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return json.dumps(self.body).encode()

def test_token_is_cached_and_secret_not_in_admin_request():
    calls = []
    def opener(req, timeout):
        calls.append(req)
        if req.full_url.endswith('/token'): return Response({'access_token':'synthetic-token','expires_in':60})
        return Response({'id':'u1'})
    policy = KeycloakEndpointPolicy('http://keycloak.test', 'kumjabar', 'idp-pegawai-admin', allow_insecure_dev=True)
    t = KeycloakHTTPTransport(policy, client_id='synthetic-client', client_secret='synthetic-secret', opener=opener)
    assert t.request('GET', policy.user_url('u1')) == {'id':'u1'}
    t.request('GET', policy.user_url('u1'))
    assert len([x for x in calls if x.full_url.endswith('/token')]) == 1
    assert 'synthetic-secret' not in calls[-1].headers.get('Authorization','')

def test_http_requires_explicit_dev_opt_in():
    import pytest
    with pytest.raises(ValueError): KeycloakEndpointPolicy('http://keycloak.test', 'r', 'c')
