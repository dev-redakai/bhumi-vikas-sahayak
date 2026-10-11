Add a deterministic calculator for a rulebook table.

1. Open the official PDF page with `pdftotext -layout -f N -l N` and transcribe the table exactly into `backend/app/calculators.py`, with rule, sub-rule and page.
2. Boundaries: copy the table's own words ("up to" = inclusive). Write a boundary test for every row in `tests/test_calculators.py`.
3. Wire it into `plan_tools()` and expose `GET /api/calc/<name>` in `backend/app/main.py` (the gateway proxies it as `/v1/calc/<name>` automatically).
4. Add a form to the Calculators page in `frontend/assets/app.js`.
