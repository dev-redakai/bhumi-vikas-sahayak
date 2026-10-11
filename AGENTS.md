# AGENTS.md — rules for coding agents (Claude Code, Cursor, Codex…) working on this repo

This repo was built agentically on 11 Oct 2026 at the Claude Impact Lab × Cerebras, Bhopal.
Read this before touching code. `CLAUDE.md` points here.

## Mission
One user, one workflow, one outcome: a **BMC building-permission clerk** asks a question in English or Hindi
and gets a short answer **with the rule number and the exact text** from the M.P. Bhumi Vikas Rules, 2012 —
or a clear **"not found"**. The tool points to the rule; the clerk decides. Don't build a portal.

## Non-negotiable rules
1. **Never invent a rule, number, page or quote.** Every citation must pass the verifier (`agents._verify`):
   the quote must appear verbatim in the rule text. Do not weaken the verifier to make output look better.
2. **Numbers from tables live in code** (`backend/app/calculators.py`), transcribed from the official PDF with
   rule, sub-rule and page. A language model never does setback or fee arithmetic.
3. **Version honesty.** The dataset is consolidated to 06-03-2025. Later changes go in `data/amendments.json`
   and are shown on every answer they touch (e.g. the 28-08-2026 change to Rule 2(5)(c)).
4. **Out of scope → "not found".** Property tax, land prices, utility bills etc. are not in this rulebook.
5. **Public data only. No personal data. No connection to any live government system.**
6. **Secrets only via environment variables** (`.env`, never committed). Check `git diff` for keys before pushing.
7. **Never edit `data/answer_key.json` to make a score go up.** It mirrors the official sample questions.

## Architecture (where to change what)
| Concern | File |
|---|---|
| LLM providers, fallback order, circuit breaker | `backend/app/llm.py` (Cerebras → Anthropic → OpenAI-compatible → offline) |
| Agent pipeline (language, scope guard, tools, retrieval, amendments, composer, verifier) | `backend/app/agents.py` |
| BM25 retrieval, chunking, page mapping, Hindi glossary | `backend/app/store.py` |
| Calculators (Rule 56 setbacks, Rule 21 fees) | `backend/app/calculators.py` |
| Internal REST API | `backend/app/main.py` (`/api/*`) |
| Public API: keys, roles, rate limits, request IDs, UI hosting | `gateway/app/main.py` (`/v1/*`) |
| Query log & dashboard aggregates | `backend/app/metrics.py` (SQLite) |
| Accuracy harness | `backend/app/evals.py`, `scripts/eval.py` |
| UI (no build step) | `frontend/index.html`, `frontend/assets/app.js`, `frontend/widget.js` |

## Workflow for every change
1. Plan in a sentence: which user-visible behaviour changes and how you will prove it.
2. Write or update a test first (`tests/`). Tests never call paid APIs; mock with `httpx.MockTransport`.
3. Implement the smallest change.
4. `make test` and `make eval` — offline accuracy must not drop. If a Cerebras key is set, also `make eval-llm`.
5. Update README ("What works / what doesn't") when behaviour changes.

## Slash commands
`.claude/commands/eval.md`, `add-amendment.md`, `new-calculator.md`.

## Style
Python 3.11+, type hints, small pure functions, no new heavy dependencies (no vector DB needed for 106 rules).
UI: vanilla JS + Tailwind CDN; keep it bilingual and readable at a busy counter.
