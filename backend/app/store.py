"""Rule store: loads the 106 rules, splits them into page-referenced chunks, and
serves BM25 retrieval. Pure Python, no vector DB, starts in well under a second."""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

from . import config

HEADER_RE = re.compile(r"^\s*Rules?\s+[\w\-–, ]+\s+M\.P\. Bhumi Vikas Rules, 2012\s+\d+\s*$", re.M)
PAGE_RE = re.compile(r"===== PDF page (\d+) =====")
TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
STOP = set("""a an the of and or to in on for by with is are be shall may as at from that this which
such any all its it into than not no if under such other per said these those has have been was were""".split())

# Hindi -> English retrieval glossary, used when no LLM is available for translation.
HI_GLOSSARY = {
    "प्लॉट": "plot", "भूखंड": "plot", "वर्ग": "square", "मीटर": "meters", "सड़क": "street road", "सडक": "street road",
    "चौड़ी": "width", "चौड़ाई": "width", "सामने": "front", "आगे": "front", "पीछे": "rear", "बगल": "side",
    "खाली": "open", "जगह": "space", "फीस": "fee fees", "शुल्क": "fee fees", "नियम": "rule", "बिल्डिंग": "building",
    "भवन": "building", "मकान": "residential building house", "घर": "residential house", "परमिशन": "permission",
    "अनुमति": "permission", "अनुज्ञा": "permission", "मंजिल": "floor storey", "ऊंचाई": "height", "ऊँचाई": "height",
    "लिफ्ट": "lift", "बालकनी": "balcony", "बिजली": "electric", "लाइन": "line", "नक्शा": "plan", "नक्शे": "plan",
    "वैध": "valid", "वैधता": "validity", "नवीनीकरण": "revalidation renew", "दस्तावेज": "documents", "दस्तावेज़": "documents",
    "पार्किंग": "parking", "फार्म": "farm", "हाउस": "house", "कृषि": "agricultural", "विकास": "development", "योजना": "plan",
    "एफएआर": "FAR", "तलघर": "basement", "बेसमेंट": "basement", "सीढ़ी": "staircase", "आवेदन": "application",
    "संपत्ति": "property", "कर": "tax", "बाजार": "market", "दर": "rate", "आवासीय": "residential", "व्यावसायिक": "commercial",
    "दुकान": "shop", "ऊँची": "high rise", "स्वीकृत": "sanctioned", "बदलाव": "deviation alteration", "परिवर्तन": "alteration",
}


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOP]


def hindi_to_english_keywords(text: str) -> str:
    out = []
    for hi, en in HI_GLOSSARY.items():
        if hi in text:
            out.append(en)
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    return " ".join(out + nums)


def _read_text(path) -> str:
    """Read a data file, falling back to its .gz twin (the repo ships the large files gzipped)."""
    import gzip
    from pathlib import Path
    path = Path(path)
    if path.exists():
        return path.read_text(encoding="utf-8")
    gz = path.with_name(path.name + ".gz")
    with gzip.open(gz, "rt", encoding="utf-8") as fh:
        return fh.read()


@dataclass
class Rule:
    rule: str
    title: str
    part: str
    page_start: int
    page_end: int
    text: str

    @property
    def clean_text(self) -> str:
        return HEADER_RE.sub("", self.text)


@dataclass
class Chunk:
    id: int
    rule: str
    title: str
    part: str
    page: int
    text: str
    tokens: list[str] = field(default_factory=list, repr=False)
    tf: Counter = field(default_factory=Counter, repr=False)


class RuleStore:
    def __init__(self) -> None:
        self.rules: dict[str, Rule] = {}
        self.order: list[str] = []
        self.pages: dict[int, str] = {}
        self.chunks: list[Chunk] = []
        self._df: Counter = Counter()
        self._avgdl = 1.0
        self._load()

    # ---------- loading ----------
    def _load(self) -> None:
        if True:
            for line in _read_text(config.RULES_FILE).splitlines():
                if not line.strip():
                    continue
                d = json.loads(line)
                r = Rule(str(d["rule"]), d["title"], d["part"], int(d["page_start"]), int(d["page_end"]), d["text"])
                self.rules[r.rule] = r
                self.order.append(r.rule)
        raw = _read_text(config.FULLTEXT_FILE)
        parts = PAGE_RE.split(raw)
        for i in range(1, len(parts) - 1, 2):
            self.pages[int(parts[i])] = parts[i + 1]
        self._build_chunks()

    def _page_for(self, rule: Rule, snippet: str) -> int:
        probe = re.sub(r"\s+", " ", snippet.strip())[:60]
        if len(probe) < 15:
            return rule.page_start
        for p in range(rule.page_start, rule.page_end + 1):
            page = re.sub(r"\s+", " ", self.pages.get(p, ""))
            if probe in page:
                return p
        return rule.page_start

    def _build_chunks(self) -> None:
        cid = 0
        for key in self.order:
            r = self.rules[key]
            text = r.clean_text
            # split on sub-rule markers "(1)", "(2)" … or blank lines; keep chunks ~900 chars
            paras = re.split(r"\n\s*\n|(?=\n\s{2,}\(\d+\)\s)", text)
            buf = ""
            for para in paras:
                if not para.strip():
                    continue
                if len(buf) + len(para) > 900 and buf:
                    self._add_chunk(cid, r, buf)
                    cid += 1
                    buf = ""
                buf += para + "\n"
            if buf.strip():
                self._add_chunk(cid, r, buf)
                cid += 1
        total = 0
        for c in self.chunks:
            for t in set(c.tokens):
                self._df[t] += 1
            total += len(c.tokens)
        self._avgdl = total / max(len(self.chunks), 1)

    def _add_chunk(self, cid: int, r: Rule, text: str) -> None:
        page = self._page_for(r, text)
        head = f"rule {r.rule} {r.title} {r.part} "
        toks = tokenize(head * 2 + text)
        self.chunks.append(Chunk(cid, r.rule, r.title, r.part, page, text.strip(), toks, Counter(toks)))

    # ---------- retrieval ----------
    def bm25(self, query: str, k: int = config.TOP_K, k1: float = 1.4, b: float = 0.75) -> list[tuple[Chunk, float]]:
        q = tokenize(query)
        if not q:
            return []
        n = len(self.chunks)
        scores: dict[int, float] = defaultdict(float)
        for c in self.chunks:
            tf = c.tf
            dl = len(c.tokens)
            s = 0.0
            for t in q:
                if t not in tf:
                    continue
                idf = math.log(1 + (n - self._df[t] + 0.5) / (self._df[t] + 0.5))
                s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * dl / self._avgdl))
            if s:
                scores[c.id] = s
        # explicit "rule 21" style mentions get a strong boost
        for m in re.findall(r"rule\s*(\d+(?:-[a-z])?)", query.lower()):
            for c in self.chunks:
                if c.rule.lower() == m:
                    scores[c.id] += 8.0
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:k]
        return [(self.chunks[i], s) for i, s in ranked]

    def search(self, query: str, k: int = 10) -> list[dict]:
        return [
            {"rule": c.rule, "title": c.title, "part": c.part, "page": c.page, "score": round(s, 3),
             "snippet": c.text[:400]}
            for c, s in self.bm25(query, k)
        ]

    # ---------- browsing ----------
    def list_rules(self) -> list[dict]:
        return [
            {"rule": r.rule, "title": r.title, "part": r.part, "page_start": r.page_start, "page_end": r.page_end,
             "chars": len(r.text)}
            for r in (self.rules[k] for k in self.order)
        ]

    def parts(self) -> list[dict]:
        grouped: dict[str, list[Rule]] = defaultdict(list)
        for k in self.order:
            grouped[self.rules[k].part].append(self.rules[k])
        out = []
        for part, rules in grouped.items():
            out.append({
                "part": part,
                "rules": [{"rule": r.rule, "title": r.title, "page_start": r.page_start} for r in rules],
                "count": len(rules),
                "pages": f"{rules[0].page_start}-{rules[-1].page_end}",
            })
        return out

    def get(self, rule: str) -> Rule | None:
        return self.rules.get(rule) or self.rules.get(rule.upper())


@lru_cache(maxsize=1)
def get_store() -> RuleStore:
    return RuleStore()
