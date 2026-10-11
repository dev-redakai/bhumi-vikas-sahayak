"""LLM provider chain with fallback and a circuit breaker.

Order (configurable with LLM_PROVIDER_ORDER):
  1. Cerebras (primary, fastest inference; several models tried in turn)
  2. Anthropic Claude
  3. Any OpenAI-compatible endpoint
  4. Offline mode: no LLM. The agent still answers with calculators + extractive citations.

A provider that errors is skipped for PROVIDER_COOLDOWN_S seconds, so a Cerebras
outage costs one timeout, not one per request."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

import httpx

from . import config


class LLMUnavailable(Exception):
    pass


@dataclass
class ProviderState:
    name: str
    configured: bool
    last_ok: float | None = None
    last_error: str | None = None
    last_error_at: float | None = None
    calls: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0
    models: list[str] = field(default_factory=list)

    @property
    def cooling_down(self) -> bool:
        return bool(self.last_error_at and time.time() - self.last_error_at < config.PROVIDER_COOLDOWN_S)

    def public(self) -> dict:
        avg = self.total_latency_ms / max(self.calls - self.failures, 1)
        if not self.configured:
            status = "not_configured"
        elif self.cooling_down:
            status = "degraded"
        else:
            status = "up" if self.last_ok or not self.last_error else "unknown"
        return {
            "name": self.name, "configured": self.configured, "status": status, "models": self.models,
            "calls": self.calls, "failures": self.failures, "avg_latency_ms": round(avg, 1),
            "last_error": self.last_error,
        }


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    latency_ms: float


class ProviderChain:
    def __init__(self) -> None:
        self.state = {
            "cerebras": ProviderState("cerebras", bool(config.CEREBRAS_API_KEY), models=config.CEREBRAS_MODELS),
            "anthropic": ProviderState("anthropic", bool(config.ANTHROPIC_API_KEY), models=[config.ANTHROPIC_MODEL]),
            "openai_compat": ProviderState("openai_compat", bool(config.OPENAI_COMPAT_API_KEY), models=[config.OPENAI_COMPAT_MODEL]),
        }
        self.client = httpx.Client(timeout=config.LLM_TIMEOUT_S)

    @property
    def any_available(self) -> bool:
        return any(s.configured for s in self.state.values())

    def health(self) -> list[dict]:
        out = [self.state[n].public() for n in config.PROVIDER_ORDER if n in self.state]
        out.append({"name": "offline", "configured": True, "status": "up", "models": ["extractive+calculators"],
                    "calls": 0, "failures": 0, "avg_latency_ms": 0, "last_error": None})
        return out

    # ---------- public ----------
    def complete(self, system: str, user: str, max_tokens: int = 900, temperature: float = 0.0,
                 json_mode: bool = False) -> LLMResponse:
        errors = []
        for name in config.PROVIDER_ORDER:
            st = self.state.get(name)
            if not st or not st.configured or st.cooling_down:
                continue
            for model in st.models:
                t0 = time.perf_counter()
                st.calls += 1
                try:
                    text = getattr(self, f"_call_{name}")(model, system, user, max_tokens, temperature, json_mode)
                    ms = (time.perf_counter() - t0) * 1000
                    st.last_ok, st.total_latency_ms = time.time(), st.total_latency_ms + ms
                    return LLMResponse(text, name, model, ms)
                except Exception as exc:  # noqa: BLE001 - any failure moves us down the chain
                    st.failures += 1
                    st.last_error = f"{model}: {type(exc).__name__}: {str(exc)[:160]}"
                    errors.append(st.last_error)
            st.last_error_at = time.time()
        raise LLMUnavailable("; ".join(errors) or "no LLM provider configured")

    # ---------- providers ----------
    def _openai_style(self, base: str, key: str, model: str, system: str, user: str, max_tokens: int,
                      temperature: float, json_mode: bool) -> str:
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_tokens if "gpt-oss" not in model else max_tokens + 1200,
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = self.client.post(f"{base.rstrip('/')}/chat/completions", json=body,
                             headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        if r.status_code == 400 and json_mode:  # some models reject response_format: retry without it
            body.pop("response_format", None)
            r = self.client.post(f"{base.rstrip('/')}/chat/completions", json=body,
                                 headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        content = msg.get("content") or ""
        if not content.strip():
            raise ValueError("empty completion")
        return content

    def _call_cerebras(self, model, system, user, max_tokens, temperature, json_mode) -> str:
        return self._openai_style(config.CEREBRAS_BASE_URL, config.CEREBRAS_API_KEY, model, system, user,
                                  max_tokens, temperature, json_mode)

    def _call_openai_compat(self, model, system, user, max_tokens, temperature, json_mode) -> str:
        return self._openai_style(config.OPENAI_COMPAT_BASE_URL, config.OPENAI_COMPAT_API_KEY, model, system, user,
                                  max_tokens, temperature, json_mode)

    def _call_anthropic(self, model, system, user, max_tokens, temperature, json_mode) -> str:
        r = self.client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": model, "max_tokens": max_tokens, "temperature": temperature, "system": system,
                  "messages": [{"role": "user", "content": user}]},
        )
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))


def parse_json(text: str) -> dict:
    """Tolerant JSON extraction from model output."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise


_chain: ProviderChain | None = None


def get_chain() -> ProviderChain:
    global _chain
    if _chain is None:
        _chain = ProviderChain()
    return _chain
