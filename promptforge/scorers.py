"""Local, dependency-free scoring functions. No APIs, no models, no keys."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ScoreResult:
    name: str
    score: float  # 0.0 - 1.0
    detail: str = ""


# -- lexicons ---------------------------------------------------------
ROAST_WORDS = {
    "roast", "burn", "savage", "destroy", "wreck", "clown", "embarrass",
    "humiliate", "spicy", "brutal", "ruthless", "clapback", "dragged",
    "obvious", "clearly", "tragic", "pathetic", "weak", "lame", "mid",
    "cringe", "suspect", "delusional", "audacity", "bold", "anyway",
}

POSITIVE_WORDS = {
    "great", "awesome", "love", "wonderful", "amazing", "brilliant",
    "fantastic", "excellent", "sweet", "kind", "nice", "best", "cool",
}

NEGATIVE_WORDS = {
    "terrible", "awful", "hate", "worst", "horrible", "stupid", "dumb",
    "ugly", "bad", "sad", "embarrassing", "cringe", "pathetic", "weak",
}

_WORD_RE = re.compile(r"[a-z']+")


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


# -- individual scorers -----------------------------------------------
def keyword_score(output: str, case) -> ScoreResult:
    """Fraction of expected keywords that appear in the output."""
    if not case.expected_keywords:
        return ScoreResult("keyword", 1.0, "no keywords required")
    hits = sum(1 for kw in case.expected_keywords if kw.lower() in output.lower())
    frac = hits / len(case.expected_keywords)
    return ScoreResult(
        "keyword", frac,
        f"{hits}/{len(case.expected_keywords)} keywords found",
    )


def length_score(output: str, case) -> ScoreResult:
    """1.0 when word count is inside [min_words, max_words], decaying outside."""
    n = len(_words(output))
    if case.min_words <= n <= case.max_words:
        return ScoreResult("length", 1.0, f"{n} words, in range")
    if n < case.min_words:
        frac = max(0.0, n / case.min_words)
        return ScoreResult("length", round(frac, 3), f"{n} words, too short")
    over = n - case.max_words
    frac = max(0.0, 1.0 - over / case.max_words)
    return ScoreResult("length", round(frac, 3), f"{n} words, too long")


def roast_score(output: str, case=None) -> ScoreResult:
    """Roast intensity: share of words from the roast lexicon (capped)."""
    words = _words(output)
    if not words:
        return ScoreResult("roast", 0.0, "empty output")
    hits = sum(1 for w in words if w in ROAST_WORDS)
    density = hits / len(words)
    score = min(1.0, density / 0.08)  # ~8% spicy words = full marks
    return ScoreResult("roast", round(score, 3), f"{hits} roast words in {len(words)}")


def structure_score(output: str, case=None) -> ScoreResult:
    """Rewards a setup/punchline shape: multiple sentences ending in a punch."""
    sentences = [s.strip() for s in re.split(r"[.!?]+", output) if s.strip()]
    if len(sentences) >= 3:
        return ScoreResult("structure", 1.0, f"{len(sentences)} sentences, clear arc")
    if len(sentences) == 2:
        return ScoreResult("structure", 0.6, "2 sentences, no full arc")
    return ScoreResult("structure", 0.2, f"{len(sentences)} sentence(s)")


def relevance_score(output: str, case) -> ScoreResult:
    """Share of the case's input words echoed in the output."""
    needles = set()
    for value in case.input.values():
        needles.update(_words(str(value)))
    needles = {w for w in needles if len(w) > 3}
    if not needles:
        return ScoreResult("relevance", 1.0, "nothing to echo")
    hay = set(_words(output))
    frac = len(needles & hay) / len(needles)
    return ScoreResult("relevance", round(frac, 3),
                       f"{len(needles & hay)}/{len(needles)} input words echoed")


def sentiment_score(output: str, case=None) -> ScoreResult:
    """Polarity balance: roasts should lean negative, not neutral mush."""
    words = _words(output)
    if not words:
        return ScoreResult("sentiment", 0.0, "empty output")
    pos = sum(1 for w in words if w in POSITIVE_WORDS)
    neg = sum(1 for w in words if w in NEGATIVE_WORDS)
    score = min(1.0, (neg - pos) / max(1, len(words)) / 0.1 + 0.5)
    return ScoreResult("sentiment", round(max(0.0, min(1.0, score)), 3),
                       f"{neg} negative / {pos} positive words")


SCORERS = {
    "keyword": keyword_score,
    "length": length_score,
    "roast": roast_score,
    "structure": structure_score,
    "relevance": relevance_score,
    "sentiment": sentiment_score,
}

DEFAULT_WEIGHTS = {
    "keyword": 0.25,
    "relevance": 0.20,
    "roast": 0.25,
    "structure": 0.15,
    "length": 0.10,
    "sentiment": 0.05,
}


def composite_score(output: str, case, weights: dict | None = None) -> tuple[float, list[ScoreResult]]:
    """Weighted composite of all scorers; returns (total, breakdown)."""
    weights = weights or DEFAULT_WEIGHTS
    breakdown = [fn(output, case) for name, fn in SCORERS.items() if name in weights]
    total = sum(r.score * weights[r.name] for r in breakdown)
    return round(total, 4), breakdown
