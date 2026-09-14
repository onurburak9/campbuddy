def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_requires_no_auth(client):
    # No login / token — the deploy health check hits this unauthenticated.
    resp = client.get("/health")
    assert resp.status_code == 200
