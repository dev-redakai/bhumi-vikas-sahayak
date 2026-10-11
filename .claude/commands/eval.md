Run the accuracy harness and report regressions.

1. `python -m pytest -q` — all tests must pass.
2. `python scripts/eval.py --offline` then, if a Cerebras key is set, `python scripts/eval.py`.
3. Compare with the committed `data/eval_report.json`. Any question that dropped from 1.0 is a regression: find the cause (retrieval, calculator, composer, verifier) before changing anything else.
4. Never edit `data/answer_key.json` to make a test pass.
