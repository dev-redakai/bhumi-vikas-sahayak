# CLAUDE.md
Follow **AGENTS.md** — it is the single source of rules for this repo.

Quick commands:
- `make dev` → UI + API on http://localhost:8080 (single process)
- `make test` → unit, agent, gateway and fallback tests
- `make eval` / `make eval-llm` → accuracy on the 17 official sample questions

Prefer Cerebras for inference (`CEREBRAS_API_KEY`); the chain falls back automatically.
