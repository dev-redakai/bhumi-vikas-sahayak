import json

from backend.app import config
from backend.app.agents import answer_question
from backend.app.evals import run_eval


def test_offline_sample_accuracy_floor():
    rep = run_eval(use_llm=False)
    assert rep["accuracy"] >= 0.9, rep


def test_not_found_for_out_of_scope():
    for q in ["How do I pay my property tax online?", "What is the weather in Bhopal?", "how to apply for passport"]:
        assert answer_question(q, use_llm=False)["not_found"]


def test_every_citation_is_verbatim():
    key = json.loads(config.ANSWER_KEY_FILE.read_text(encoding="utf-8"))
    for item in key:
        r = answer_question(item["question"], use_llm=False)
        for c in r["citations"]:
            assert c["verified"] is True
            assert c["pdf_url"].startswith(config.OFFICIAL_PDF_EN)


def test_amendment_flagged_for_small_plot_question():
    r = answer_question("Do I need separate development permission for a 300 sq m plot that matches the Development Plan?", use_llm=False)
    assert any(a["id"] == "2026-08-28-rule-2-5-c" for a in r["amendments"])
    assert "2026-08-28" in r["rules_version"]


def test_hindi_answer_in_hindi():
    r = answer_question("मेरा प्लॉट 200 वर्ग मीटर का है और सामने 9 मीटर चौड़ी सड़क है। आगे कितनी जगह खाली छोड़नी होगी?", use_llm=False)
    assert r["language"] == "hi" and "3.0" in r["answer"] and "मीटर" in r["answer"]
