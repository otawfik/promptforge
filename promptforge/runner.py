"""Eval runner: run prompt versions against test sets, compare, rank."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field

from .datasets import TestSet
from .models import LocalResponder
from .scorers import composite_score, ScoreResult
from .store import PromptVersion


@dataclass
class CaseResult:
    case_id: str
    output: str
    total: float
    breakdown: list[ScoreResult]
    latency_ms: float

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "output": self.output,
            "total": self.total,
            "latency_ms": self.latency_ms,
            "breakdown": [asdict(b) for b in self.breakdown],
        }


@dataclass
class EvalResult:
    prompt_name: str
    prompt_version: int
    test_set: str
    mean_score: float
    cases: list[CaseResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "prompt_name": self.prompt_name,
            "prompt_version": self.prompt_version,
            "test_set": self.test_set,
            "mean_score": self.mean_score,
            "cases": [c.to_dict() for c in self.cases],
        }


def run_eval(prompt: PromptVersion, test_set: TestSet, backend=None,
             weights: dict | None = None, progress=None) -> EvalResult:
    """Render the prompt for every case, generate, and score."""
    backend = backend or LocalResponder()
    results = []
    for i, case in enumerate(test_set.cases):
        rendered = prompt.render(**case.input)
        t0 = time.perf_counter()
        output = backend.respond(rendered, case.input)
        latency = (time.perf_counter() - t0) * 1000
        total, breakdown = composite_score(output, case, weights)
        results.append(CaseResult(case.id, output, total, breakdown, latency))
        if progress:
            progress(i + 1, len(test_set.cases))
    mean = round(sum(r.total for r in results) / len(results), 4) if results else 0.0
    return EvalResult(prompt.name, prompt.version, test_set.name, mean, results)


def ab_compare(prompts: list[PromptVersion], test_set: TestSet, backend=None,
               weights: dict | None = None) -> list[EvalResult]:
    """Run several prompt versions head-to-head; best mean score first."""
    results = [run_eval(p, test_set, backend, weights) for p in prompts]
    return sorted(results, key=lambda r: r.mean_score, reverse=True)


class Leaderboard:
    """Persistent ranking of every eval run, best score first."""

    def __init__(self, path: str | None = None):
        self.path = path
        self._runs: list[dict] = []
        if path and os.path.exists(path):
            with open(path) as f:
                self._runs = json.load(f)

    def record(self, result: EvalResult):
        self._runs.append(result.to_dict())
        self._save()

    def ranked(self) -> list[dict]:
        return sorted(self._runs, key=lambda r: r["mean_score"], reverse=True)

    def best(self) -> dict | None:
        ranked = self.ranked()
        return ranked[0] if ranked else None

    def _save(self):
        if not self.path:
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._runs, f, indent=2)
