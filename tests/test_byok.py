"""Bring-your-own-key: per-request provider keys from the Settings page."""
from fastapi.testclient import TestClient

from backend.app.llm import _safe_base, overrides_from_headers
from gateway.app.main import app

c = TestClient(app)
UI = {"X-API-Key": "bvs-web-ui"}


def test_health_reports_own_key_without_echoing_it():
    secret = "csk-test-not-a-real-key-123"
    h = c.get("/v1/health", headers={**UI, "X-BVS-Cerebras-Key": secret}).json()
    cer = next(p for p in h["providers"] if p["name"] == "cerebras")
    assert cer["configured"] and cer["source"] == "your key"
    assert secret not in c.get("/v1/health", headers={**UI, "X-BVS-Cerebras-Key": secret}).text


def test_without_header_server_config_applies():
    h = c.get("/v1/health", headers=UI).json()
    cer = next(p for p in h["providers"] if p["name"] == "cerebras")
    assert cer["source"] in ("server", "none")


def test_llm_test_endpoint_no_keys():
    r = c.post("/v1/llm/test", headers=UI, json={"providers": ["anthropic"]}).json()
    assert r["results"][0]["ok"] is False


def test_unsafe_base_urls_rejected():
    assert _safe_base("http://api.example.com/v1") is None
    assert _safe_base("https://localhost/v1") is None
    assert _safe_base("https://10.0.0.5/v1") is None
    assert _safe_base("https://api.groq.com/openai/v1") == "https://api.groq.com/openai/v1"
    o = overrides_from_headers({"x-bvs-openai-base": "https://127.0.0.1/v1", "x-bvs-provider-order": "openai_compat,evil"})
    assert "openai_base" not in o and o["order"] == ["openai_compat"]
