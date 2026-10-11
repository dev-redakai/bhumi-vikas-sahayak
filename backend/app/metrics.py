"""Query log + aggregates for the dashboard and reports. SQLite, zero setup."""
from __future__ import annotations

import csv
import io
import json
import sqlite3
import statistics
import threading
import time
from collections import Counter

from . import config

_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    config.DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(config.DB_FILE, check_same_thread=False)
    c.execute("""CREATE TABLE IF NOT EXISTS queries (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, question TEXT, language TEXT, answer TEXT,
        not_found INTEGER, confidence TEXT, provider TEXT, model TEXT, latency_ms REAL,
        rules TEXT, client TEXT, feedback INTEGER)""")
    return c


def log_query(res: dict, client: str = "web") -> int:
    rules = sorted({c.get("rule") for c in res.get("citations", []) if c.get("rule")})
    with _lock, _conn() as c:
        cur = c.execute(
            "INSERT INTO queries (ts, question, language, answer, not_found, confidence, provider, model, latency_ms, rules, client) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (time.time(), res["question"], res["language"], res["answer"], int(res["not_found"]), res["confidence"],
             res["provider"], res["model"], res["latency_ms"], json.dumps(rules), client),
        )
        return cur.lastrowid


def set_feedback(qid: int, helpful: bool) -> None:
    with _lock, _conn() as c:
        c.execute("UPDATE queries SET feedback=? WHERE id=?", (1 if helpful else -1, qid))


def recent(limit: int = 100) -> list[dict]:
    with _conn() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT * FROM queries ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["rules"] = json.loads(d["rules"] or "[]")
        out.append(d)
    return out


def stats() -> dict:
    rows = recent(5000)
    lat = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
    by_day: Counter = Counter()
    for r in rows:
        by_day[time.strftime("%Y-%m-%d %H:00", time.localtime(r["ts"]))] += 1
    rule_counts: Counter = Counter(rule for r in rows for rule in r["rules"])
    fb = [r["feedback"] for r in rows if r["feedback"]]
    return {
        "total_queries": len(rows),
        "answered": sum(1 for r in rows if not r["not_found"]),
        "not_found": sum(1 for r in rows if r["not_found"]),
        "languages": dict(Counter(r["language"] for r in rows)),
        "providers": dict(Counter(r["provider"] for r in rows)),
        "confidence": dict(Counter(r["confidence"] for r in rows)),
        "clients": dict(Counter(r["client"] for r in rows)),
        "latency_ms": {
            "p50": round(statistics.median(lat), 1) if lat else 0,
            "p95": round(sorted(lat)[int(len(lat) * 0.95) - 1], 1) if len(lat) >= 2 else (lat[0] if lat else 0),
            "avg": round(sum(lat) / len(lat), 1) if lat else 0,
        },
        "timeline": [{"bucket": k, "count": v} for k, v in sorted(by_day.items())][-48:],
        "top_rules": [{"rule": k, "count": v} for k, v in rule_counts.most_common(10)],
        "helpful_rate": round(sum(1 for f in fb if f > 0) / len(fb), 3) if fb else None,
    }


def export_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "time", "language", "question", "answer", "not_found", "confidence", "provider", "model", "latency_ms", "rules", "client", "feedback"])
    for r in recent(10000):
        w.writerow([r["id"], time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"])), r["language"], r["question"],
                    r["answer"], r["not_found"], r["confidence"], r["provider"], r["model"], r["latency_ms"],
                    " ".join(r["rules"]), r["client"], r["feedback"]])
    return buf.getvalue()
