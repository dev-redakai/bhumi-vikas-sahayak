"""Run the 17-question accuracy harness. Usage: python scripts/eval.py [--offline]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.evals import run_eval  # noqa: E402

rep = run_eval(use_llm="--offline" not in sys.argv)
print(f"mode={rep['mode']} accuracy={rep['accuracy']:.0%} score={rep['score']}/{rep['questions']} "
      f"rule_hit={rep['rule_accuracy']:.0%} avg_latency={rep['avg_latency_ms']}ms")
for r in rep["rows"]:
    flag = "OK " if r["score"] == 1 else "~~ " if r["score"] else "XX "
    print(f"{flag} Q{r['id']:>2} cited={','.join(r['cited_rules']) or '-':<12} {r['question'][:70]}")
