"""LLM provider chain with fallback and a circuit breaker.

Order (configurable with LLM_PROVIDER_ORDER):
  1. Cerebras (primary, fastest inference; several models tried in turn)
  2. Anthropic Claude
  3. Any OpenAI-compatible endpoint
  4. Offline mode: no LLM. The agent still answers with calculators + extractive citations.

A provider that errors is skipped for PROVIDER_COOLDOWN_S seconds, so a Cerebras
outage costs one timeout, not one per request."""
from __future__ import annotations

import contextvars
import ipaddress
import json
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from . import config


class LLMUnavailable(Exception):
    pass


# ---------------------------------------------------------------------------
# Bring-your-own-key (BYOK): a UI user (or a partner portal) can send their own
# provider keys per request as headers. They live only for that request, in this
# context variable, and are never logged, stored, or echoed back.
# ---------------------------------------------------------------------------
_overrides: contextvars.ContextVar[dict] = contextvars.ContextVar("bvs_llm_overrides", default={})

BYOK_HEADERS = {
    "x-bvs-cerebras-key": "cerebras_key",
    "x-bvs-cerebras-model": "cerebras_model",
    "x-bvs-anthropic-key": "anthropic_key",
    "x-bvs-anthropic-model": "anthropic_model",
    "x-bvs-openai-key": "openai_key",
    "x-bvs-openai-base": "openai_base",
    "x-bvs-openai-model": "openai_model",
    "x-bvs-provider-order": "order",
}


def _safe_base(url: str) -> str | None:
    """Only public https endpoints may be supplied by a caller (prevents SSRF into the server's network)."""
    try:
        u = urlparse(url.strip())
    except ValueError:
        return None
    if u.scheme != "https" or not u.hostname:
        return None
    host = u.hostname.lower()
    if host in ("localhost",) or host.endswith((".local", ".internal")):
        return None
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return None
    except ValueError:
        pass
    return url.strip().rstrip("/")


def overrides_from_headers(headers) -> dict:
    out: dict = {}
    for h, k in BYOK_HEADERS.items():
        v = (headers.get(h) or "").strip()
        if not v or len(v) > 400:
            continue
        if k == "order":
            out[k] = [x.strip() for x in v.split(",") if x.strip() in ("cerebras", "anthropic", "openai_compat")]
        elif k == "openai_base":
            b = _safe_base(v)
            if b:
                out[k] = b
        else:
            out[k] = v
    return out


def set_overrides(d: dict):
    return _overrides.set(d)


def reset_overrides(token) -> None:
    _overrides.reset(token)


def current_overrides() -> dict:
    return _overrides.get()


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

    # ---------- resolution: server env keys, overridden per request by BYOK headers ----------
    def resolve(self, name: str) -> dict:
        o = current_overrides()
        if name == "cerebras":
            key = o.get("cerebras_key") or config.CEREBRAS_API_KEY
            models = [o["cerebras_model"]] + [m for m in config.CEREBRAS_MODELS if m != o["cerebras_model"]] \
                if o.get("cerebras_model") else config.CEREBRAS_MODELS
            return {"key": key, "models": models, "base": config.CEREBRAS_BASE_URL, "byok": bool(o.get("cerebras_key"))}
        if name == "anthropic":
            return {"key": o.get("anthropic_key") or config.ANTHROPIC_API_KEY,
                    "models": [o.get("anthropic_model") or config.ANTHROPIC_MODEL], "base": "https://api.anthropic.com",
                    "byok": bool(o.get("anthropic_key"))}
        if name == "openai_compat":
            byok = bool(o.get("openai_key"))
            return {"key": o.get("openai_key") or config.OPENAI_COMPAT_API_KEY,
                    "models": [o.get("openai_model") or config.OPENAI_COMPAT_MODEL],
                    "base": (o.get("openai_base") if byok else None) or config.OPENAI_COMPAT_BASE_URL, "byok": byok}
        return {"key": "", "models": [], "base": "", "byok": False}

    def order(self) -> list[str]:
        return current_overrides().get("order") or config.PROVIDER_ORDER

    @property
    def any_available(self) -> bool:
        return any(self.resolve(n)["key"] for n in self.state)

    def health(self) -> list[dict]:
        out = []
        for n in self.order():
            if n not in self.state:
                continue
            p = self.state[n].public()
            r = self.resolve(n)
            if r["byok"]:  # caller's own key: report it as configured, never the key itself
                p.update(configured=True, status="up" if p["status"] in ("not_configured", "unknown", "up") else p["status"],
                         models=r["models"], source="your key")
            else:
                p["source"] = "server" if p["configured"] else "none"
            out.append(p)
        out.append({"name": "offline", "configured": True, "status": "up", "models": ["extractive+calculators"],
                    "calls": 0, "failures": 0, "avg_latency_ms": 0, "last_error": None})
        return out

    # ---------- public ----------
    def complete(self, system: str, user: str, max_tokens: int = 900, temperature: float = 0.0,
                 json_mode: bool = False, only: list[str] | None = None) -> LLMResponse:
        errors = []
        for name in (only or self.order()):
            st = self.state.get(name)
            if not st:
                continue
            r = self.resolve(name)
            # the circuit breaker protects the server's shared key; a caller's own key is always tried
            if not r["key"] or (st.cooling_down and not r["byok"]):
                continue
            for model in r["models"]:
                t0 = time.perf_counter()
                st.calls += 1
                try:
                    text = getattr(self, f"_call_{name}")(r, model, system, user, max_tokens, temperature, json_mode)
                    ms = (time.perf_counter() - t0) * 1000
                    st.last_ok, st.total_latency_ms = time.time(), st.total_latency_ms + ms
                    return LLMResponse(text, name, model, ms)
                except Exception as exc:  # noqa: BLE001 - any failure moves us down the chain
                    st.failures += 1
                    msg = str(exc)[:160].replace(r["key"], "***") if r["key"] else str(exc)[:160]
                    st.last_error = f"{model}: {type(exc).__name__}: {msg}"
                    errors.append(st.last_error)
                    code = getattr(getattr(exc, "response", None), "status_code", None)
                    if code in (401, 403):  # a bad key fails for every model: don't retry the others
                        break
            if not r["byok"]:
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

    def _call_cerebras(self, r, model, system, user, max_tokens, temperature, json_mode) -> str:
        return self._openai_style(r["base"], r["key"], model, system, user, max_tokens, temperature, json_mode)

    def _call_openai_compat(self, r, model, system, user, max_tokens, temperature, json_mode) -> str:
        return self._openai_style(r["base"], r["key"], model, system, user, max_tokens, temperature, json_mode)

    def _call_anthropic(self, rv, model, system, user, max_tokens, temperature, json_mode) -> str:
        r = self.client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": rv["key"], "anthropic-version": "2023-06-01",
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
