.PHONY: install dev backend gateway test eval eval-llm
install: ; pip install -r requirements-dev.txt
dev: ; uvicorn gateway.app.main:app --reload --port 8080           # UI + API at http://localhost:8080
backend: ; uvicorn backend.app.main:app --reload --port 8000
gateway: ; BACKEND_URL=http://localhost:8000 uvicorn gateway.app.main:app --reload --port 8080
test: ; python -m pytest -q
eval: ; python scripts/eval.py --offline
eval-llm: ; python scripts/eval.py
