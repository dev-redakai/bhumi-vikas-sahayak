"""API Gateway – the single public entry point.

* Versioned public API under /v1/* that any portal (MPSeDC, BMC e-Nagarpalika, a mobile app) can call
* API-key auth (X-API-Key or Authorization: Bearer), per-key roles and per-key rate limits
* Request IDs, timing, usage metering, CORS, and the web UI + embeddable widget
* Proxies to the backend over HTTP (BACKEND_URL) or, when BACKEND_URL is empty, mounts it in-process
  so the whole system also runs as a single container.
"""
from __future__ import annotations

import os
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
BACKEND_URL = os.getenv("BACKEND_URL", "").rstrip("/")
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))
UI_KEY = os.getenv("GATEWAY_UI_KEY", "bvs-web-ui")

# GATEWAY_API_KEYS="mpsedc:sk_live_abc:partner,ops:sk_admin_xyz:admin"
def _load_keys() -> dict[str, dict]:
    keys = {UI_KEY: {"name": "web-ui", "role": "ui"}}
    raw = os.getenv("GATEWAY_API_KEYS", "demo:bvs-demo-key:partner")
    for item in filter(None, (x.strip() for x in raw.split(","))):
        parts = item.split(":")
        if len(parts) >= 2:
            keys[parts[1]] = {"name": parts[0], "role": parts[2] if len(parts) > 2 else "partner"}
    return keys


API_KEYS = _load_keys()
PUBLIC_PATHS = {"/v1/health", "/v1/openapi.json"}
PARTNER_ALLOWED = ("ask", "search", "rules", "parts", "amendments", "calc/", "summaries/", "health", "feedback")
ADMIN_ONLY = ("eval/run",)

_buckets: dict[str, deque] = defaultdict(deque)
_usage: dict[str, dict] = defaultdict(lambda: {"requests": 0, "errors": 0, "total_ms": 0.0, "last_seen": None})

app = FastAPI(title="Bhumi Vikas Sahayak – Public API Gateway", version="1.0.0",
              description="Public API for rule-grounded answers on the M.P. Bhumi Vikas Rules, 2012. "
                          "Authenticate with `X-API-Key`. See /docs for the full contract.",
              docs_url="/docs", openapi_url="/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["X-Request-ID", "X-RateLimit-Remaining", "X-Upstream-Latency-ms"])

if BACKEND_URL:
    _client = httpx.AsyncClient(base_url=BACKEND_URL, timeout=90)
else:  # monolith mode: call the backend ASGI app directly, no network hop
    from backend.app.main import app as backend_app
    from backend.app.main import _warm
    _warm()
    _client = httpx.AsyncClient(transport=httpx.ASGITransport(app=backend_app), base_url="http://backend", timeout=90)


def _rate_ok(key: str) -> tuple[bool, int]:
    now = time.time()
    q = _buckets[key]
    while q and now - q[0] > 60:
        q.popleft()
    limit = RATE_LIMIT_PER_MIN * (5 if API_KEYS.get(key, {}).get("role") in ("ui", "admin") else 1)
    if len(q) >= limit:
        return False, 0
    q.append(now)
    return True, limit - len(q)


def _key_from(request: Request) -> str | None:
    k = request.headers.get("x-api-key")
    if not k:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            k = auth[7:].strip()
    return k or request.query_params.get("api_key")


@app.api_route("/v1/{path:path}", methods=["GET", "POST"])
async def proxy(path: str, request: Request):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    full = f"/v1/{path}"
    key = _key_from(request)
    ident = API_KEYS.get(key or "")
    if full not in PUBLIC_PATHS:
        if not ident:
            return JSONResponse({"error": "unauthorized", "message": "Send a valid X-API-Key header."}, 401,
                                headers={"X-Request-ID": rid})
        role = ident["role"]
        if role == "partner" and not path.startswith(PARTNER_ALLOWED):
            return JSONResponse({"error": "forbidden", "message": f"Key role '{role}' cannot call {full}"}, 403,
                                headers={"X-Request-ID": rid})
        if role not in ("admin", "ui") and path.startswith(ADMIN_ONLY):
            return JSONResponse({"error": "forbidden"}, 403, headers={"X-Request-ID": rid})
        ok, remaining = _rate_ok(key)
        if not ok:
            return JSONResponse({"error": "rate_limited", "message": f"Limit {RATE_LIMIT_PER_MIN}/min"}, 429,
                                headers={"X-Request-ID": rid, "Retry-After": "60"})
    else:
        remaining = -1
    name = ident["name"] if ident else "public"

    body = await request.body()
    if path == "ask" and body:  # tag the caller so dashboards can split traffic by portal
        import json as _json
        try:
            payload = _json.loads(body)
            payload["client"] = name
            body = _json.dumps(payload).encode()
        except ValueError:
            pass
    t0 = time.perf_counter()
    try:
        upstream = await _client.request(request.method, f"/api/{path}", params=request.query_params,
                                         content=body, headers={"content-type": request.headers.get("content-type", "application/json"),
                                                                "x-request-id": rid})
    except httpx.HTTPError as exc:
        _usage[name]["errors"] += 1
        return JSONResponse({"error": "upstream_unavailable", "detail": str(exc)[:200]}, 502, headers={"X-Request-ID": rid})
    ms = (time.perf_counter() - t0) * 1000
    u = _usage[name]
    u["requests"] += 1
    u["total_ms"] += ms
    u["last_seen"] = time.time()
    if upstream.status_code >= 400:
        u["errors"] += 1
    headers = {"X-Request-ID": rid, "X-Upstream-Latency-ms": f"{ms:.1f}", "X-RateLimit-Remaining": str(remaining)}
    for h in ("content-disposition",):
        if h in upstream.headers:
            headers[h] = upstream.headers[h]
    return Response(upstream.content, upstream.status_code, headers=headers,
                    media_type=upstream.headers.get("content-type", "application/json"))


@app.get("/gateway/usage")
async def usage(request: Request):
    ident = API_KEYS.get(_key_from(request) or "")
    if not ident or ident["role"] not in ("admin", "ui"):
        return JSONResponse({"error": "unauthorized"}, 401)
    return {"rate_limit_per_min": RATE_LIMIT_PER_MIN, "mode": "proxy" if BACKEND_URL else "monolith",
            "consumers": [{"name": n, **v, "avg_ms": round(v["total_ms"] / max(v["requests"], 1), 1)} for n, v in _usage.items()]}


@app.get("/config.js", response_class=PlainTextResponse)
async def config_js():
    return PlainTextResponse(f"window.BVS_CONFIG={{apiBase:'/v1',apiKey:'{UI_KEY}'}};", media_type="application/javascript")


@app.get("/widget.js")
async def widget():
    return FileResponse(FRONTEND / "widget.js", media_type="application/javascript")


app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")


@app.get("/")
async def index():
    return FileResponse(FRONTEND / "index.html")
