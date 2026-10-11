# Architecture

```
 Portal / mobile app / WhatsApp bot          Clerk's browser (UI, widget)
              │  X-API-Key                           │
              ▼                                      ▼
 ┌──────────────────────── API GATEWAY  (gateway/app/main.py, :8080) ────────────────────────┐
 │  /v1/*  auth (keys+roles) · rate limit · request-id · usage metering · CORS · UI/widget   │
 └──────────────────────────────────────┬───────────────────────────────────────────────────┘
                                        │ HTTP (BACKEND_URL)  or  in-process ASGI (monolith)
 ┌──────────────────────── BACKEND  (backend/app/main.py, :8000) ───────────────────────────┐
 │  /api/ask ──► Agent pipeline (agents.py)                                                  │
 │     1 LanguageAgent ─ 2 ScopeGuard ─ 3 Planner/Tools ─ 4 Retriever ─ 5 Amendments          │
 │     6 Composer (LLM chain) ─ 7 Verifier (quotes must be verbatim)                          │
 │  /api/rules /api/search /api/parts /api/calc/* /api/summaries/* /api/stats /api/eval ...   │
 └──────┬──────────────────┬───────────────────┬──────────────────────────┬──────────────────┘
        ▼                  ▼                   ▼                          ▼
  RuleStore (BM25,   Calculators          LLM ProviderChain           SQLite query log
  347 page-mapped    R56 setbacks,        Cerebras → Anthropic →      (dashboards, reports,
  chunks, 106 rules) R21 fees             OpenAI-compat → offline     CSV export, feedback)
```

## Why these choices
- **Cerebras first**: the clerk needs an answer within a minute while a citizen waits; Cerebras inference keeps the
  full 7-step pipeline well under that. Models are tried in order (`CEREBRAS_MODELS`).
- **Fallback + circuit breaker**: a failing provider is skipped for 60 s, so an outage costs one timeout, not one per request.
  If every LLM is down, **offline mode** still answers from calculators + verified extractive quotes (17/17 on the samples).
- **BM25, not a vector DB**: 106 rules fit in memory; BM25 is exact on rule vocabulary ("open space", "revalidation"),
  starts in 0.1 s, and needs no embedding API.
- **Verifier**: the jury and the clerk need to trust citations. Any quote not found verbatim in the rule text is dropped.
- **Amendments layer**: the data stops at 06-03-2025; `data/amendments.json` carries later changes and every answer
  states which version it used.
