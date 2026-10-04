"""Test sets: collections of eval cases a prompt version runs against."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class TestCase:
    """A single eval case: inputs to render into the prompt template."""

    id: str
    input: dict
    expected_keywords: list[str] = field(default_factory=list)
    min_words: int = 8
    max_words: int = 200
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, row: dict) -> "TestCase":
        return cls(
            id=row["id"],
            input=row.get("input", {}),
            expected_keywords=row.get("expected_keywords", []),
            min_words=row.get("min_words", 8),
            max_words=row.get("max_words", 200),
            tags=row.get("tags", []),
        )


@dataclass
class TestSet:
    """A named bundle of test cases."""

    name: str
    description: str = ""
    cases: list[TestCase] = field(default_factory=list)

    @classmethod
    def from_json(cls, path: str) -> "TestSet":
        with open(path) as f:
            data = json.load(f)
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            cases=[TestCase.from_dict(row) for row in data["cases"]],
        )

    def filter(self, tag: str) -> "TestSet":
        return TestSet(
            name=f"{self.name} [{tag}]",
            description=self.description,
            cases=[c for c in self.cases if tag in c.tags],
        )

    def __len__(self) -> int:
        return len(self.cases)


def load_roast_battle(path: str | None = None) -> TestSet:
    """Load the bundled roast-battle test set."""
    if path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(os.path.dirname(here), "data", "roast_battle.json")
    return TestSet.from_json(path)
