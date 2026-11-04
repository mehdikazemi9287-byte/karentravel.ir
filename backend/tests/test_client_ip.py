from types import SimpleNamespace

from app.main import _client_ip


def req(peer, headers=None):
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers={k.lower(): v for k, v in (headers or {}).items()})


def test_behind_private_proxy_uses_last_forwarded_hop():
    assert _client_ip(req("172.18.0.5", {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"})) == "5.6.7.8"   # spoofed first hop ignored
    assert _client_ip(req("127.0.0.1", {"X-Real-IP": "9.9.9.9"})) == "9.9.9.9"
    assert _client_ip(req("172.18.0.5", {"X-Forwarded-For": "garbage"})) == "172.18.0.5"


def test_public_peer_ignores_forwarded_headers():
    assert _client_ip(req("8.8.8.8", {"X-Forwarded-For": "1.1.1.1"})) == "8.8.8.8"
    assert _client_ip(req("testclient")) == "testclient"
