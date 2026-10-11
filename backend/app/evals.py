"""Accuracy harness over the 17 official sample questions (data/answer_key.json).

A question scores 1.0 when: the right rule is cited AND every expected number appears
in the answer AND (for out-of-scope questions) the tool says not found.
Partial credit: 0.5 for the right rule without all numbers."""
from __future__ import annotations

import json
import re
import time

from . import config
from .agents import answer_question


WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "ten": "10",
         "एक": "1", "दो": "2", "तीन": "3", "पांच": "5", "पाँच": "5"}


def _has_number(text: str, num: str) -> bool:
    n = float(num)
    for w, d in WORDS.items():
        text = re.sub(rf"\b{w}\b", d, text, flags=re.I) if w.isascii() else text.replace(w, d)
    for m in re.findall(r"\d+(?:[.,]\d+)?", text.replace(",", "")):
        try:
            if abs(float(m) - n) < 1e-9:
                return True
        except ValueError:
            continue
    return False


def run_eval(use_llm: bool = True) -> dict:
    key = json.loads(config.ANSWER_KEY_FILE.read_text(encoding="utf-8"))
    rows, t0 = [], time.perf_counter()
    for item in key:
        res = answer_question(item["question"], use_llm=use_llm)
        cited = {c["rule"] for c in res["citations"]}
        blob = res["answer"] + " " + " ".join(str(c.get("value")) for c in res["calculations"]) + " " + \
            " ".join(c.get("quote", "") for c in res["citations"])
        if item["not_found"]:
            score = 1.0 if res["not_found"] else 0.0
            rule_ok = nums_ok = res["not_found"]
        else:
            rule_ok = bool(set(item["expect_rules"]) & cited) and not res["not_found"]
            nums_ok = all(_has_number(blob, n) for n in item["expect_numbers"])
            if item.get("expect_amendment"):
                nums_ok = nums_ok and any(a["id"] == item["expect_amendment"] for a in res["amendments"])
            score = 1.0 if rule_ok and nums_ok else 0.5 if rule_ok else 0.0
        rows.append({
            "id": item["id"], "lang": item["lang"], "question": item["question"], "expected_rules": item["expect_rules"],
            "cited_rules": sorted(cited), "rule_ok": rule_ok, "numbers_ok": nums_ok, "not_found_expected": item["not_found"],
            "not_found_returned": res["not_found"], "score": score, "answer": res["answer"],
            "provider": res["provider"], "latency_ms": res["latency_ms"],
        })
    total = sum(r["score"] for r in rows)
    report = {
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "mode": "llm" if use_llm else "offline",
        "questions": len(rows),
        "score": total,
        "accuracy": round(total / len(rows), 3),
        "rule_accuracy": round(sum(1 for r in rows if r["rule_ok"]) / len(rows), 3),
        "not_found_correct": sum(1 for r in rows if r["not_found_expected"] and r["not_found_returned"]),
        "false_not_found": sum(1 for r in rows if not r["not_found_expected"] and r["not_found_returned"]),
        "avg_latency_ms": round(sum(r["latency_ms"] for r in rows) / len(rows), 1),
        "duration_s": round(time.perf_counter() - t0, 2),
        "rows": rows,
    }
    config.EVAL_REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def last_report() -> dict | None:
    try:
        return json.loads(config.EVAL_REPORT_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
