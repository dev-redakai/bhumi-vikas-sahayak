"""Provider chain: Cerebras first, fallback on failure, verifier drops invented quotes."""
import json

import httpx

from backend.app import agents, config, llm


def _chain_with(handler, monkeypatch, cerebras=True, anthropic=False):
    monkeypatch.setattr(config, "CEREBRAS_API_KEY", "x" if cerebras else "")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "y" if anthropic else "")
    monkeypatch.setattr(config, "OPENAI_COMPAT_API_KEY", "")
    chain = llm.ProviderChain()
    chain.client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(llm, "_chain", chain)
    monkeypatch.setattr(agents, "get_chain", lambda: chain)
    return chain


def _openai_reply(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_cerebras_answer_is_used_and_fake_quote_dropped(monkeypatch):
    payload = {
        "answer": "Leave 3.6 m at the front (Rule 56(1)(a)).", "not_found": False, "confidence": "high",
        "citations": [
            {"rule": "56", "sub_rule": "56(1)(a)", "page": 77, "quote": "Every Residential Building having height up to 12.5 meters, facing street shall have a front open space"},
            {"rule": "56", "sub_rule": "56(9)", "page": 77, "quote": "this sentence does not exist in the rulebook at all"},
        ],
    }

    def handler(req: httpx.Request):
        assert "cerebras" in str(req.url)
        return _openai_reply(json.dumps(payload))

    _chain_with(handler, monkeypatch)
    r = agents.answer_question("My house faces a 10 m wide street and will be 9 m tall. Front open space?")
    assert r["provider"] == "cerebras"
    quotes = [c["quote"] for c in r["citations"]]
    assert any("front open space" in q for q in quotes)
    assert not any("does not exist" in q for q in quotes)


def test_falls_back_to_anthropic_then_offline(monkeypatch):
    calls = []

    def handler(req: httpx.Request):
        calls.append(str(req.url))
        if "cerebras" in str(req.url):
            return httpx.Response(503, json={"error": "overloaded"})
        return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps({
            "answer": "1.50 m rear open space.", "not_found": False, "confidence": "high",
            "citations": [{"rule": "56", "page": 78, "quote": "Every Residential Building, having height up to 12.5 meters, shall have a Rear Open Space"}]})}]})

    _chain_with(handler, monkeypatch, anthropic=True)
    r = agents.answer_question("What is the minimum rear open space for a 150 sq m residential plot?")
    assert r["provider"] == "anthropic"
    assert any("cerebras" in u for u in calls)


def test_all_providers_down_still_answers_offline(monkeypatch):
    _chain_with(lambda req: httpx.Response(500), monkeypatch)
    r = agents.answer_question("What is the minimum rear open space for a 150 sq m residential plot?")
    assert r["provider"] == "offline" and "1.5" in r["answer"]
