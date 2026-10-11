import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("BVS_DB_FILE", os.path.join(tempfile.mkdtemp(), "test.db"))
# tests never call paid LLM APIs
for k in ("CEREBRAS_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_COMPAT_API_KEY"):
    os.environ.pop(k, None)
