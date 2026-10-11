"""The answering agent: a small, inspectable multi-step pipeline.

  1. LanguageAgent   detect English/Hindi; translate Hindi to English for retrieval
  2. ScopeGuard      catch questions the rulebook cannot answer (property tax, land rates…)
  3. Planner/Tools   pick deterministic calculators (setbacks, fees) from the question
  4. Retriever       BM25 over page-referenced rule chunks, with query expansion
  5. AmendmentAgent  attach rule changes made after the 06-03-2025 consolidation
  6. Composer        LLM (Cerebras → fallbacks) writes a short answer from the evidence only
  7. Verifier        every quote must appear verbatim in the retrieved text, else it is dropped

Every step is timed and returned as a trace, so the clerk (and the jury) can see why."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

from . import config
from .calculators import CalcResult, plan_tools
from .llm import LLMUnavailable, get_chain, parse_json
from .store import Chunk, get_store, hindi_to_english_keywords, tokenize

DEVANAGARI = re.compile(r"[\u0900-\u097F]")

OUT_OF_SCOPE = [
    (r"property tax|house tax|सम्पत्ति कर|संपत्ति कर|प्रॉपर्टी टैक्स", "property tax"),
    (r"market (rate|price|value)|circle rate|guideline (rate|value)|land (rate|price)|बाजार (दर|भाव|मूल्य)|कलेक्टर गाइडलाइन", "land prices"),
    (r"electricity bill|water bill|बिजली बिल|पानी बिल", "utility bills"),
    (r"pay .* online|online payment|ऑनलाइन (भुगतान|जमा)", "online payments"),
    (r"loan|emi|interest rate|बैंक लोन", "loans"),
]

EXPANSIONS = {
    r"setback|gap|leave .* front|margin": "open space front rear side",
    r"renew|renewal|extend|extension": "revalidation duration of sanction valid",
    r"valid|validity|expire|lapse": "duration of sanction revalidation",
    r"not replied|no reply|deadline|miss the deadline|delay": "limitation period grant refusal deemed permission",
    r"sign|submit .* plans|who can (sign|submit)": "preparation and signing of plans licensing architect engineer",
    r"documents?|papers": "information accompanying application documents",
    r"change .* plan|modify .* plan|after .* sanction": "deviation from sanctioned plan alteration",
    r"disagree|conflict|prevail|override": "provisions of development plan to take precedence",
    r"farm ?house": "permission of farm house agricultural",
    r"\blifts?\b|elevator": "provision of lifts escalators",
    r"balcony|electric|power line|overhead": "distance from electric lines overhead",
    r"floors?|storey|how (high|tall)": "height limit floor area ratio",
    r"\bfar\b|floor area ratio": "floor area ratio",
    r"fee|fees|charges?": "fees permission fee application fee",
    r"separate development permission|development permission": "permission for development plot development plan",
    r"parking": "parking space",
    r"basement": "basement",
}

SYSTEM_PROMPT = """You are Bhumi Vikas Sahayak, an assistant for a building-permission clerk at the Bhopal Municipal Corporation.
You answer ONLY from the EVIDENCE given (excerpts of the M.P. Bhumi Vikas Rules, 2012 consolidated to 06-03-2025, tracked amendments, and calculator results computed in code).
Hard rules:
- Never invent a rule, number, page or quote. If the evidence does not answer the question, set "not_found": true and say so plainly.
- Every factual statement must be backed by a citation whose "quote" is copied VERBATIM (a short span, max ~200 chars) from an evidence excerpt.
- Numbers from tables: prefer the CALCULATOR results; they are already correct.
- If an AMENDMENT applies, the amended rule wins; say which version you used.
- Answer in the user's language ({lang_name}); quotes stay in English as printed.
- Be short: 2-5 sentences a clerk can read aloud in under a minute. Not legal advice; the clerk decides.
Return ONLY JSON:
{{"answer": "...", "not_found": false, "confidence": "high|medium|low",
  "citations": [{{"rule": "56", "sub_rule": "56(1)(a)", "page": 77, "quote": "verbatim span"}}],
  "follow_up": "one short clarifying question if an input is missing, else empty"}}"""


@dataclass
class Trace:
    steps: list = field(default_factory=list)

    def add(self, name: str, t0: float, **detail) -> None:
        self.steps.append({"step": name, "ms": round((time.perf_counter() - t0) * 1000, 1), **detail})


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def detect_language(q: str) -> str:
    return "hi" if DEVANAGARI.search(q) else "en"


def expand_query(q_en: str) -> str:
    extra = [v for pat, v in EXPANSIONS.items() if re.search(pat, q_en, re.I)]
    return q_en + " " + " ".join(extra)


SPLIT_RE = re.compile(r"(?<=[;:])\s+|(?<=[a-z0-9\]\)]{2}\.)\s+|\n(?=\s*\()")


def _sentences(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", x).strip() for x in SPLIT_RE.split(text) if x and x.strip()]


def _span_scores(sentences: list[str], query: str) -> list[float]:
    qt = set(tokenize(query))
    wants_number = bool(re.search(r"how (long|many|much|far)|minimum|maximum|fee|size|far\b|distance|vertical|horizontal|valid|renew|kitna|kitni|कितन", query, re.I))
    out = []
    for i, own in enumerate(sentences):
        sc = len(qt & set(tokenize(own)))
        if i + 1 < len(sentences):
            sc += 0.4 * len(qt & set(tokenize(sentences[i + 1])))
        if wants_number and re.search(r"\d+(\.\d+)?\s*(m\b|meters?|metres?|hectare|years?|%|sq|rs)", own, re.I):
            sc += 2.5
        elif wants_number and re.search(r"\d+\.\d+", own):
            sc += 1.5
        if "COMMENTS" in own or re.search(r"\bVs\.|MPLJ|MANISA", own):
            sc -= 10
        out.append(sc)
    return out


def best_sentence(text: str, query: str, max_len: int = 320) -> str:
    spans = best_spans(text, query, n=1, max_len=max_len)
    return spans[0] if spans else text[:max_len]


def best_spans(text: str, query: str, title: str = "", n: int = 2, max_len: int = 320) -> list[str]:
    """Top-n distinct verbatim spans in document order; court-case comments and the heading are skipped."""
    body = re.sub(r"^\s*\d+[\-A-Za-z]*\.\s*[^.]{0,120}?\.-\s*", "", text, count=1)
    body = body.split("COMMENTS")[0] or body
    sents = _sentences(body)
    if not sents:
        return []
    scores = _span_scores(sents, query)
    ranked = sorted(range(len(sents)), key=lambda i: -scores[i])
    chosen: list[int] = []
    for i in ranked:
        if len(chosen) >= n or scores[i] <= 0 and chosen:
            break
        if any(abs(i - j) <= 0 for j in chosen) or len(sents[i]) < 20:
            continue
        chosen.append(i)
    out = []
    for i in sorted(chosen):
        span = sents[i]
        if len(span) < 120 and i + 1 < len(sents) and i + 1 not in chosen:
            span += " " + sents[i + 1]
        out.append(span[:max_len])
    return out


def load_amendments() -> list[dict]:
    try:
        return json.loads(config.AMENDMENTS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []


def matching_amendments(q: str, retrieved_rules: set[str]) -> list[dict]:
    out = []
    ql = q.lower()
    for a in load_amendments():
        hit = any(t.lower() in ql for t in a.get("triggers", []))
        area = re.search(r"(\d+(?:\.\d+)?)\s*(?:sq|वर्ग)", ql)
        if area and float(area.group(1)) <= 500 and "development permission" in ql:
            hit = True
        if hit:
            out.append(a)
    return out


def answer_question(question: str, lang_hint: str | None = None, use_llm: bool = True) -> dict:
    t_start = time.perf_counter()
    trace = Trace()
    store = get_store()
    chain = get_chain()

    # 1. language
    t0 = time.perf_counter()
    lang = lang_hint if lang_hint in ("en", "hi") else detect_language(question)
    q_en = question
    translated_by = "none"
    if lang == "hi":
        q_en = hindi_to_english_keywords(question)
        translated_by = "glossary"
        if use_llm and chain.any_available:
            try:
                r = chain.complete("Translate the user's Hindi question about building rules into precise English. Reply with the English sentence only.",
                                   question, max_tokens=200)
                q_en = r.text.strip() + " " + q_en
                translated_by = f"{r.provider}:{r.model}"
            except LLMUnavailable:
                pass
    trace.add("language", t0, lang=lang, english_query=q_en[:200], translated_by=translated_by)

    # 2. scope guard
    t0 = time.perf_counter()
    oos = next((label for pat, label in OUT_OF_SCOPE if re.search(pat, question + " " + q_en, re.I)), None)
    trace.add("scope_guard", t0, out_of_scope=oos)
    if oos:
        return _not_found(question, lang, trace, t_start, reason=f"The Bhumi Vikas Rules do not cover {oos}.")

    # 3. tools
    t0 = time.perf_counter()
    calcs: list[CalcResult] = plan_tools(q_en, question)
    trace.add("planner_tools", t0, tools=[c.tool for c in calcs])

    # 4. retrieval
    t0 = time.perf_counter()
    expanded = expand_query(q_en)
    hits = store.bm25(expanded, k=config.TOP_K)
    # make sure calculator rules are in the evidence
    have = {c.rule for c, _ in hits}
    for calc in calcs:
        if calc.rule not in have:
            extra = [c for c in store.chunks if c.rule == calc.rule and c.page == calc.page][:1]
            hits += [(c, 0.0) for c in extra]
    top_score = hits[0][1] if hits else 0.0
    trace.add("retriever", t0, top_score=round(top_score, 2),
              hits=[{"rule": c.rule, "page": c.page, "score": round(s, 2)} for c, s in hits])

    # 5. amendments
    t0 = time.perf_counter()
    amends = matching_amendments(question + " " + q_en, {c.rule for c, _ in hits})
    for a in amends:
        anc = a.get("anchor") or {}
        extra = [c for c in store.chunks if c.rule == anc.get("rule") and anc.get("contains", "") in re.sub(r"\s+", " ", c.text)][:1]
        hits = [(c, 9.9) for c in extra] + [h for h in hits if h[0].id not in {e.id for e in extra}]
    trace.add("amendments", t0, applied=[a["id"] for a in amends])

    if not calcs and top_score < config.MIN_RETRIEVAL_SCORE:
        return _not_found(question, lang, trace, t_start, reason="No rule in the rulebook matches this question closely enough.")

    # 6. compose
    t0 = time.perf_counter()
    provider, model, result = "offline", "extractive", None
    if use_llm and chain.any_available:
        try:
            result, provider, model = _compose_llm(chain, question, lang, hits, calcs, amends)
        except (LLMUnavailable, ValueError, KeyError, json.JSONDecodeError) as exc:
            trace.steps.append({"step": "composer_fallback", "ms": 0, "error": str(exc)[:200]})
    if result is None:
        result = _compose_offline(question, q_en, lang, hits, calcs, amends)
    trace.add("composer", t0, provider=provider, model=model)

    # 7. verify
    t0 = time.perf_counter()
    result, dropped = _verify(result, hits, calcs)
    trace.add("verifier", t0, verified=len(result["citations"]), dropped=dropped)

    return {
        "question": question,
        "language": lang,
        "answer": result["answer"],
        "not_found": bool(result.get("not_found")),
        "confidence": result.get("confidence", "medium"),
        "citations": result["citations"],
        "calculations": [c.dict() for c in calcs],
        "amendments": amends,
        "follow_up": result.get("follow_up", ""),
        "provider": provider,
        "model": model,
        "rules_version": config.RULES_VERSION + (" + amendment " + ", ".join(a["date"] for a in amends) if amends else ""),
        "latency_ms": round((time.perf_counter() - t_start) * 1000, 1),
        "trace": trace.steps,
        "disclaimer": "Points to the rule; the clerk decides. Not legal advice.",
    }


def _evidence_block(hits: list[tuple[Chunk, float]], calcs: list[CalcResult], amends: list[dict]) -> str:
    parts = []
    for i, (c, _) in enumerate(hits, 1):
        parts.append(f"[E{i}] Rule {c.rule} — {c.title} (PDF page {c.page})\n{c.text[:1400]}")
    for c in calcs:
        parts.append(f"[CALC] {c.tool}: value={c.value} {c.unit}. {c.explanation} Source: Rule {c.sub_rule}, PDF page {c.page}, table row: {c.table_row}")
    for a in amends:
        parts.append(f"[AMENDMENT {a['date']}] Rule {a['sub_rule']}: {a['summary']} ({a['verification']})")
    return "\n\n".join(parts)


def _compose_llm(chain, question, lang, hits, calcs, amends):
    system = SYSTEM_PROMPT.format(lang_name="Hindi (Devanagari)" if lang == "hi" else "English")
    user = f"QUESTION: {question}\n\nEVIDENCE:\n{_evidence_block(hits, calcs, amends)}"
    r = chain.complete(system, user, max_tokens=700, json_mode=True)
    data = parse_json(r.text)
    data.setdefault("citations", [])
    if not isinstance(data.get("answer"), str):
        raise ValueError("bad answer field")
    return data, r.provider, r.model


def _compose_offline(question, q_en, lang, hits, calcs, amends) -> dict:
    lines, cites = [], []
    for c in calcs:
        lines.append(c.explanation_hi if lang == "hi" else c.explanation)
    for a in amends:
        lines.append(("संशोधन " + a["date"] + ": " + a["summary_hi"]) if lang == "hi" else f"Amendment of {a['date']}: {a['summary']}")
    anchored = [h for h in hits if h[1] == 9.9]
    top = anchored[:1] + hits[1:2] if anchored else hits[:2] if not calcs else [h for h in hits if h[0].rule in {c.rule for c in calcs}][:1] or hits[:1]
    store = get_store()
    seen_rules = []
    for j, (c, _) in enumerate(top):
        if c.rule in seen_rules:
            continue
        seen_rules.append(c.rule)
        rule = store.get(c.rule)
        # read the whole rule when it is short, so a table header and its rows stay together
        ctx = rule.clean_text if rule and len(rule.clean_text) < 4000 else "\n".join(h.text for h, _ in hits if h.rule == c.rule)
        for quote in best_spans(ctx, q_en, c.title, n=3 if j == 0 else 1):
            page = store._page_for(rule, quote) if rule else c.page
            cites.append({"rule": c.rule, "sub_rule": c.rule, "page": page, "quote": quote})
    if not lines:
        c = top[0][0]
        q = " … ".join(x["quote"] for x in cites if x["rule"] == c.rule)
        lines.append((f"नियम {c.rule} – {c.title} (पृष्ठ {c.page}) के अनुसार: “{q}”") if lang == "hi"
                     else f"Per Rule {c.rule} – {c.title} (PDF page {c.page}): “{q}”")
    return {"answer": " ".join(lines), "not_found": False, "confidence": "high" if calcs else "medium",
            "citations": cites, "follow_up": ""}


def _verify(result: dict, hits, calcs) -> tuple[dict, int]:
    corpus = {c.rule: _norm(c.text) for c, _ in hits}
    all_text = " ".join(corpus.values())
    store = get_store()
    good, dropped = [], 0
    for cit in result.get("citations", []):
        quote = _norm(str(cit.get("quote", "")))
        rule = str(cit.get("rule", "")).strip()
        full_rule = _norm(store.get(rule).text) if store.get(rule) else ""
        if len(quote) >= 8 and (quote in all_text or quote in full_rule):
            r = store.get(rule)
            if r and not (r.page_start <= int(cit.get("page") or 0) <= r.page_end):
                cit["page"] = r.page_start
            cit["verified"] = True
            if r:
                cit["title"] = r.title
            good.append(cit)
        else:
            dropped += 1
    for c in calcs:  # calculator tables are always citable
        if not any(g.get("rule") == c.rule for g in good):
            good.append({"rule": c.rule, "sub_rule": c.sub_rule, "page": c.page, "quote": c.table_row,
                         "verified": True, "title": store.get(c.rule).title if store.get(c.rule) else "", "kind": "table"})
    result["citations"] = good
    if not good and not result.get("not_found"):
        result["confidence"] = "low"
    for g in good:
        g["pdf_url"] = f"{config.OFFICIAL_PDF_EN}#page={g.get('page', 1)}"
    return result, dropped


def _not_found(question: str, lang: str, trace: Trace, t_start: float, reason: str) -> dict:
    msg_hi = "भूमि विकास नियम, 2012 में इस प्रश्न का उत्तर नहीं मिला। कृपया संबंधित विभाग से संपर्क करें।"
    return {
        "question": question, "language": lang,
        "answer": msg_hi if lang == "hi" else f"Not found in the M.P. Bhumi Vikas Rules, 2012. {reason} Please refer the citizen to the relevant department.",
        "not_found": True, "confidence": "high", "citations": [], "calculations": [], "amendments": [],
        "follow_up": "", "provider": "guard", "model": "rules", "rules_version": config.RULES_VERSION,
        "latency_ms": round((time.perf_counter() - t_start) * 1000, 1), "trace": trace.steps,
        "disclaimer": "Points to the rule; the clerk decides. Not legal advice.",
    }
