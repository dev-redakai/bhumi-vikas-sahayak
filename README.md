# भूमि विकास सहायक · Bhumi Vikas Sahayak

**Ask the Bhopal building rulebook in English or Hindi, and get an answer with the rule number, the page and the exact text.**

Claude Impact Lab × Cerebras Café Compute, Bhopal, 11 Oct 2026 · **Track 1: Bhumi Vikas Sahayak**

| | |
|---|---|
| **Team** | _Team name_ (edit) |
| **Members** | Manikant Goutam (tech lead), _add teammates_ |
| **The one user** | A building-permission clerk at the Bhopal Municipal Corporation counter, answering a citizen within a minute |
| **Outcome** | Short answer in the citizen's language, with rule number, PDF page and verbatim quote, plus correct table numbers. Says "not found" when the rules are silent |

## Why clerks can trust it
- **Every answer is cited and verified.** Each quote must appear word for word in the rule text, or the verifier drops it. The PDF link opens on the right page.
- **Table maths happens in code.** Rule 56 setbacks and Rule 21 fees are transcribed from the official PDF with row and page, then computed deterministically.
- **It knows what changed.** The data stops at 06-03-2025. The **28-08-2026 amendment to Rule 2(5)(c)** (plots up to 500 sq m need no separate development permission) is tracked and flagged on every answer it affects.
- **It says "not found".** Property tax, land rates and similar questions are refused instead of guessed.
- **Hindi in, Hindi out.** The official Hindi PDF uses a legacy font that can't be parsed, so we retrieve on the English text and answer in Devanagari.
- **Accuracy is measured.** The 17 official sample questions score **100% in offline mode** (right rule + every expected number + correct "not found"s). See `data/eval_report.json` and the Reports page.

## Run it (5 steps)
```bash
git clone https://github.com/dev-redakai/bhumi-vikas-sahayak.git && cd bhumi-vikas-sahayak
pip install -r requirements.txt
cp .env.example .env            # add CEREBRAS_API_KEY (optional: ANTHROPIC_API_KEY as fallback)
set -a; . ./.env; set +a
uvicorn gateway.app.main:app --port 8080      # open http://localhost:8080
```
Docker: `docker build -t bvs . && docker run -p 8080:8080 --env-file .env bvs`. Split services: `docker compose up`.
It runs **with no API key at all** (offline mode: calculators plus verified extractive answers).

## Settings, your own AI key, and the built-in guide

- **⚙️ Settings & API keys**: paste a Cerebras key (recommended), plus optional Anthropic or OpenAI-compatible backups, pick the model and fallback order, then click **Save & test connection**. Keys stay in your browser (session-only unless you tick *Remember*). They are sent only with your own requests as `X-BVS-*` headers, used for that one request, and never stored or logged by the server. With no key at all, the app runs in offline mode and still answers with citations.
- **🧭 How to use / उपयोग गाइड**: an "I want to… → go here" task map, every page explained, how to read an answer card, 4-step AI setup, and an FAQ, all in English and Hindi.
- Every page opens with a dismissible bilingual 💡 tip. A first-visit welcome tour explains the app in 3 steps. EN / हिं / EN+हिं buttons switch the interface language.

## What's inside
| Layer | What it does |
|---|---|
| **UI** (`frontend/`) | Ask (chat with citations, calculators, amendment banners, agent trace, copy-for-citizen, 👍/👎) · **Dashboard** (KPIs, questions over time, outcomes, language, provider split, top rules, provider health, API consumers) · **Rule explorer** (106 rules by Part, full-text search, AI summary per rule) · **Calculators** · **Summaries** (amendment tracker, rulebook at a glance, counter cheat-sheet) · **Reports** (accuracy table, re-run eval, query log, CSV export, operational summary) · **API & integrate** (docs, live tester, widget snippet). Bilingual, dark/light, mobile. |
| **Gateway** (`gateway/`) | Public `/v1` API for any portal: API keys with roles, per-key rate limits, request IDs, usage metering, CORS, OpenAPI at `/docs`, embeddable `widget.js` |
| **Backend** (`backend/`) | 7-step agent: language → scope guard → calculator tools → BM25 retrieval → amendments → LLM composer → verifier |
| **LLM chain** | **Cerebras** (`gpt-oss-120b` → `llama-3.3-70b` → `qwen-3-32b`) → Anthropic Claude → any OpenAI-compatible API → offline. Circuit breaker skips a failing provider for 60 s |

Docs: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · [`docs/API.md`](docs/API.md) · agent rules in [`AGENTS.md`](AGENTS.md)

```bash
curl -X POST http://localhost:8080/v1/ask -H "X-API-Key: bvs-demo-key" -H "Content-Type: application/json" \
     -d '{"question":"मेरा प्लॉट 200 वर्ग मीटर का है और सामने 9 मीटर चौड़ी सड़क है। आगे कितनी जगह खाली छोड़नी होगी?"}'
```

## What works
- All 17 sample questions answered correctly offline, including Hindi Q14/Q15, the Q11 amendment, and both "not found" cases.
- Calculators: front open space (Rule 56(1)(a)), rear open space (56(2)(a)), building-permission fee (21(2), 21(3)(b)/(c)) with use types and high-rise.
- Provider fallback, tested with mocks: Cerebras failure → Anthropic → offline (`tests/test_fallback.py`).
- 18 automated tests plus a CI workflow.

## What doesn't (yet)
- The Rule 42 Tables 4/5 (open spaces above 12.5 m) and the Rule 53 / 61 FAR tables are not yet calculators. Answers from them are extractive, so check against the PDF.
- The 2026 amendment comes from secondary sources (TeamLease RegTech, MTP News). The Gazette text is not attached.
- The Hindi PDF is not parsed (legacy font). Hindi quotes come from the English rules.
- The Q4 day count lives in Section 30(5) of the Adhiniyam, not in these rules, so the tool deliberately doesn't state it.
- Accuracy with an LLM depends on the key and model configured. Run `make eval-llm` to measure.
- Dashboard data is a local SQLite log. There's no user login (the gateway uses API keys).

## Data used
- Participant pack: MP Bhumi Vikas Rules 2012, consolidated to 06-03-2025 ([English PDF](https://mptownplan.gov.in/NewsPDF/bvn06032025E.pdf), [Hindi PDF](https://mptownplan.gov.in/NewsPDF/bvn06032025H.pdf)), split by the organisers into `data/bhumi_vikas_rules.jsonl.gz` (gzipped to keep the repo light) ([pack](https://github.com/Laaaaksh/bhopal-impact-lab-2026))
- Extra public data, the 28-08-2026 amendment to Rule 2(5)(c): [TeamLease RegTech](https://teamleaseregtech.com/updates/article/59469/government-of-madhya-pradesh-amendment-to-land-development-rules), [MTP News](https://mtpnews.in/path-cleared-for-building-houses-on-plots-up-to-500-sq-m-in-mp-no-development-permission-required-from-tcp/)
- No personal data. No connection to any government system.

## How it was built
Built agentically during the event (all code written after 10:15 AM, 11 Oct 2026). We read the full 108-page rulebook against the 17 sample questions to build a verified answer key, transcribed the tables into calculators, wrote tests first, and iterated on the eval harness. See `AGENTS.md` and `.claude/commands/`.

**Not legal advice. The tool points to the rule; the clerk decides.** Licensed under [MIT](LICENSE).
