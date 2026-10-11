import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("BVS_DB_FILE", os.path.join(tempfile.mkdtemp(), "test.db"))
# tests never call paid LLM APIs
for k in ("CEREBRAS_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_COMPAT_API_KEY"):
    os.environ.pop(k, None)
# gateway keys and monolith mode must be set before any test module imports the gateway
os.environ.setdefault("GATEWAY_API_KEYS", "demo:test-partner:partner,ops:test-admin:admin")
os.environ["BACKEND_URL"] = ""
