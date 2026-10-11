"""Backend API (internal). The public, key-protected surface is the gateway (gateway/app/main.py)."""
from __future__ import annotations

import json
import re
import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from . import calculators, config, evals, metrics
from .agents import answer_question, load_amendments
from .llm import LLMUnavailable, get_chain, overrides_from_headers, reset_overrides, set_overrides
from .store import get_store

app = FastAPI(title="Bhumi Vikas Sahayak – Backend", version="1.0.0",
              description="Rule-grounded answers on the M.P. Bhumi Vikas Rules, 2012 for BMC building-permission clerks.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class BYOKMiddleware:
    """Pure ASGI middleware: lifts X-BVS-* provider-key headers into a request-scoped context variable."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode(errors="ignore") for k, v in scope.get("headers", [])}
        token = set_overrides(overrides_from_headers(headers))
        try:
            await self.app(scope, receive, send)
        finally:
            reset_overrides(token)


app.add_middleware(BYOKMiddleware)

_summary_cache: dict[str, dict] = {}


class AskIn(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    language: str | None = Field(None, description="'en' or 'hi'; auto-detected when omitted")
    use_llm: bool = True
    client: str = "web"


class FeedbackIn(BaseModel):
    query_id: int
    helpful: bool


@app.on_event("startup")
def _warm() -> None:
    get_store()
    get_chain()


@app.get("/api/health")
def health():
    s = get_store()
    return {"status": "ok", "rules": len(s.rules), "chunks": len(s.chunks), "rules_version": config.RULES_VERSION,
            "providers": get_chain().health(), "time": time.time()}


@app.post("/api/ask")
def ask(body: AskIn):
    res = answer_question(body.question.strip(), body.language, body.use_llm)
    res["query_id"] = metrics.log_query(res, body.client)
    return res


class LLMTestIn(BaseModel):
    providers: list[str] = Field(default_factory=lambda: ["cerebras", "anthropic", "openai_compat"])


@app.post("/api/llm/test")
def llm_test(body: LLMTestIn):
    """Check each provider with a one-word prompt, using the caller's own keys when sent (Settings page)."""
    chain = get_chain()
    out = []
    for name in body.providers:
        if name not in chain.state:
            continue
        r = chain.resolve(name)
        if not r["key"]:
            out.append({"provider": name, "ok": False, "source": "none", "message": "No key set"})
            continue
        try:
            resp = chain.complete("Reply with the single word OK.", "Say OK.", max_tokens=8, only=[name])
            out.append({"provider": name, "ok": True, "source": "your key" if r["byok"] else "server",
                        "model": resp.model, "latency_ms": round(resp.latency_ms), "message": "Connected"})
        except LLMUnavailable as exc:
            msg = str(exc)
            if "401" in msg or "403" in msg:
                msg = "Key rejected by the provider (401/403). Check that it was copied fully. · कुंजी अस्वीकार हुई, पूरी कॉपी करके दोबारा डालें।"
            elif "404" in msg:
                msg = "Model not available for this key (404). Pick another model. · यह मॉडल उपलब्ध नहीं, दूसरा चुनें।"
            elif "429" in msg:
                msg = "Rate limit reached (429). Wait a minute and retry. · सीमा पूरी, एक मिनट बाद फिर कोशिश करें।"
            else:
                msg = msg[:240]
            out.append({"provider": name, "ok": False, "source": "your key" if r["byok"] else "server", "message": msg})
    return {"results": out}


@app.post("/api/feedback")
def feedback(body: FeedbackIn):
    metrics.set_feedback(body.query_id, body.helpful)
    return {"ok": True}


@app.get("/api/search")
def search(q: str = Query(..., min_length=2), k: int = 10):
    return {"query": q, "results": get_store().search(q, k)}


@app.get("/api/rules")
def rules():
    return {"rules": get_store().list_rules()}


@app.get("/api/rules/{rule_id}")
def rule(rule_id: str):
    r = get_store().get(rule_id)
    if not r:
        raise HTTPException(404, f"Rule {rule_id} not found")
    amends = [a for a in load_amendments() if r.rule in a.get("affects_rules", [])]
    return {"rule": r.rule, "title": r.title, "part": r.part, "page_start": r.page_start, "page_end": r.page_end,
            "text": r.clean_text, "amendments": amends, "pdf_url": f"{config.OFFICIAL_PDF_EN}#page={r.page_start}"}


@app.get("/api/parts")
def parts():
    return {"parts": get_store().parts()}


@app.get("/api/amendments")
def amendments():
    return {"amendments": load_amendments(), "base_version": config.RULES_VERSION}


# ---------- calculators ----------
@app.get("/api/calc/front-open-space")
def calc_front(street_width_m: float = Query(..., gt=0), height_m: float | None = None):
    return calculators.front_open_space(street_width_m, height_m).dict()


@app.get("/api/calc/rear-open-space")
def calc_rear(plot_area_sqm: float = Query(..., gt=0), height_m: float | None = None):
    return calculators.rear_open_space(plot_area_sqm, height_m).dict()


@app.get("/api/calc/permission-fee")
def calc_fee(built_up_sqm: float = Query(..., gt=0), use: str = "residential", height_m: float | None = None):
    return calculators.building_permission_fee(built_up_sqm, use, height_m).dict()


# ---------- summaries ----------
@app.get("/api/summaries/rule/{rule_id}")
def summarize_rule(rule_id: str, language: str = "en"):
    r = get_store().get(rule_id)
    if not r:
        raise HTTPException(404, "rule not found")
    ck = f"{r.rule}:{language}"
    hit = _summary_cache.get(ck)
    # an AI summary is reused by everyone; an offline one is retried as soon as an AI key is available
    if hit and (hit["provider"] != "offline" or not get_chain().any_available):
        return hit
    text = r.clean_text[:9000]
    out = None
    chain = get_chain()
    if chain.any_available:
        try:
            resp = chain.complete(
                "Summarise this rule of the M.P. Bhumi Vikas Rules, 2012 for a municipal clerk. Use only the text given. "
                "Return JSON: {\"summary\": \"3-4 sentences\", \"key_numbers\": [\"short fact with number\"], \"watch_out\": \"one caveat\"}. "
                + ("Write in Hindi (Devanagari)." if language == "hi" else "Write in English."),
                f"Rule {r.rule} – {r.title}\n\n{text}", max_tokens=600, json_mode=True)
            from .llm import parse_json
            d = parse_json(resp.text)
            out = {"rule": r.rule, "title": r.title, "summary": d.get("summary", ""), "key_numbers": d.get("key_numbers", []),
                   "watch_out": d.get("watch_out", ""), "provider": resp.provider, "model": resp.model}
        except (LLMUnavailable, ValueError, json.JSONDecodeError):
            out = None
    if out is None:  # extractive fallback
        sents = re.split(r"(?<=[.;])\s+", re.sub(r"\s+", " ", text))
        nums = [s.strip()[:160] for s in sents if re.search(r"\d+(\.\d+)?\s*(m|meters?|sq|%|Rs|hectare|years?)", s)][:5]
        out = {"rule": r.rule, "title": r.title, "summary": " ".join(sents[:3])[:600], "key_numbers": nums,
               "watch_out": "Extractive summary (no LLM configured). Verify against the PDF.", "provider": "offline", "model": "extractive"}
    out["page_start"], out["page_end"] = r.page_start, r.page_end
    _summary_cache[ck] = out
    return out


# ---------- dashboard & reports ----------
@app.get("/api/stats")
def stats():
    s = metrics.stats()
    s["providers_health"] = get_chain().health()
    rep = evals.last_report()
    s["eval"] = {k: rep[k] for k in ("accuracy", "rule_accuracy", "score", "questions", "mode", "run_at")} if rep else None
    return s


@app.get("/api/queries")
def queries(limit: int = 100):
    return {"queries": metrics.recent(limit)}


@app.get("/api/queries.csv", response_class=PlainTextResponse)
def queries_csv():
    return PlainTextResponse(metrics.export_csv(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=bvs_queries.csv"})


@app.get("/api/eval")
def eval_last():
    return evals.last_report() or {"message": "no eval run yet"}


@app.post("/api/eval/run")
def eval_run(use_llm: bool = True):
    return evals.run_eval(use_llm=use_llm)


@app.get("/api/reports/summary")
def report_summary():
    """A one-page operational summary: usage, quality, coverage, open gaps."""
    s = metrics.stats()
    rep = evals.last_report()
    unanswered = [q["question"] for q in metrics.recent(500) if q["not_found"]][:15]
    low_conf = [q["question"] for q in metrics.recent(500) if q["confidence"] == "low"][:15]
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rules_version": config.RULES_VERSION,
        "usage": {k: s[k] for k in ("total_queries", "answered", "not_found", "languages", "clients", "latency_ms")},
        "quality": {"eval": rep and {k: rep[k] for k in ("accuracy", "rule_accuracy", "score", "questions", "mode", "run_at")},
                    "helpful_rate": s["helpful_rate"], "confidence": s["confidence"]},
        "coverage": {"top_rules": s["top_rules"], "amendments_tracked": len(load_amendments())},
        "gaps": {"unanswered_questions": unanswered, "low_confidence_questions": low_conf},
    }
