"""Central configuration. Every secret comes from environment variables, never from code."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("BVS_DATA_DIR", ROOT / "data"))

RULES_FILE = DATA_DIR / "bhumi_vikas_rules.jsonl"
FULLTEXT_FILE = DATA_DIR / "bhumi_vikas_rules_fulltext_by_page.txt"
AMENDMENTS_FILE = DATA_DIR / "amendments.json"
ANSWER_KEY_FILE = DATA_DIR / "answer_key.json"
EVAL_REPORT_FILE = DATA_DIR / "eval_report.json"
DB_FILE = Path(os.getenv("BVS_DB_FILE", DATA_DIR / "app.db"))

RULES_VERSION = "MP Bhumi Vikas Rules 2012, consolidated to 06-03-2025 (+ tracked amendments)"
OFFICIAL_PDF_EN = "https://mptownplan.gov.in/NewsPDF/bvn06032025E.pdf"
OFFICIAL_PDF_HI = "https://mptownplan.gov.in/NewsPDF/bvn06032025H.pdf"


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# --- LLM providers, tried in this order. Cerebras is primary. ---
CEREBRAS_API_KEY = _env("CEREBRAS_API_KEY")
CEREBRAS_BASE_URL = _env("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
# comma-separated: the first available model wins, the rest are tried on error
CEREBRAS_MODELS = [m.strip() for m in _env("CEREBRAS_MODELS", "gpt-oss-120b,llama-3.3-70b,qwen-3-32b").split(",") if m.strip()]

ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-sonnet-4-5")

# Any OpenAI-compatible endpoint (OpenAI, Groq, OpenRouter, local vLLM/Ollama)
OPENAI_COMPAT_API_KEY = _env("OPENAI_COMPAT_API_KEY")
OPENAI_COMPAT_BASE_URL = _env("OPENAI_COMPAT_BASE_URL", "https://api.openai.com/v1")
OPENAI_COMPAT_MODEL = _env("OPENAI_COMPAT_MODEL", "gpt-4o-mini")

PROVIDER_ORDER = [p.strip() for p in _env("LLM_PROVIDER_ORDER", "cerebras,anthropic,openai_compat").split(",") if p.strip()]
LLM_TIMEOUT_S = float(_env("LLM_TIMEOUT_S", "25"))
# After a provider fails, skip it for this many seconds (circuit breaker)
PROVIDER_COOLDOWN_S = float(_env("PROVIDER_COOLDOWN_S", "60"))

TOP_K = int(_env("BVS_TOP_K", "6"))
# Below this BM25 score (and with no calculator match) the question is treated as outside the rules.
MIN_RETRIEVAL_SCORE = float(_env("BVS_MIN_SCORE", "9.0"))
