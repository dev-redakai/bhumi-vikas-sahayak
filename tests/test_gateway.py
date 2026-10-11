import os

os.environ.setdefault("GATEWAY_API_KEYS", "demo:test-partner:partner,ops:test-admin:admin")
os.environ["BACKEND_URL"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from gateway.app.main import app  # noqa: E402

client = TestClient(app)


def test_health_is_public():
    assert client.get("/v1/health").status_code == 200


def test_auth_required():
    assert client.post("/v1/ask", json={"question": "fee?"}).status_code == 401


def test_partner_can_ask_but_not_read_logs():
    h = {"X-API-Key": "test-partner"}
    r = client.post("/v1/ask", json={"question": "rear open space for 150 sq m plot", "use_llm": False}, headers=h)
    assert r.status_code == 200 and r.json()["citations"]
    assert "X-Request-ID" in r.headers
    assert client.get("/v1/queries", headers=h).status_code == 403


def test_admin_reads_stats_and_usage():
    h = {"X-API-Key": "test-admin"}
    assert client.get("/v1/stats", headers=h).status_code == 200
    assert client.get("/gateway/usage", headers=h).status_code == 200


def test_ui_served():
    assert client.get("/").status_code == 200
    assert "BVS_CONFIG" in client.get("/config.js").text
