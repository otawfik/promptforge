"""Prompt versioning: register, evolve, and diff prompt templates."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class PromptVersion:
    """One version of a named prompt template."""

    name: str
    version: int
    template: str
    description: str = ""
    tags: list = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def render(self, **kwargs) -> str:
        """Render the template with the given variables."""
        return self.template.format(**kwargs)


class PromptStore:
    """File-backed store of versioned prompt templates.

    Every call to :meth:`register` with an existing name bumps the version
    number, so prompts evolve like code: nothing is overwritten, and any
    historical version can be re-run and diffed.
    """

    def __init__(self, path: str | None = None):
        self.path = path
        self._versions: list[PromptVersion] = []
        if path and os.path.exists(path):
            self._load()

    # -- writes -------------------------------------------------------
    def register(self, name: str, template: str, description: str = "",
                 tags: list | None = None) -> PromptVersion:
        """Register a new prompt, or a new version of an existing one."""
        latest = self.latest(name)
        version = (latest.version + 1) if latest else 1
        pv = PromptVersion(
            name=name,
            version=version,
            template=template,
            description=description,
            tags=tags or [],
        )
        self._versions.append(pv)
        self._save()
        return pv

    # -- reads --------------------------------------------------------
    def names(self) -> list[str]:
        seen = []
        for pv in self._versions:
            if pv.name not in seen:
                seen.append(pv.name)
        return seen

    def versions(self, name: str) -> list[PromptVersion]:
        return [pv for pv in self._versions if pv.name == name]

    def latest(self, name: str) -> PromptVersion | None:
        matches = self.versions(name)
        return max(matches, key=lambda pv: pv.version) if matches else None

    def get(self, name: str, version: int | None = None) -> PromptVersion:
        pv = self.latest(name) if version is None else next(
            (p for p in self._versions if p.name == name and p.version == version),
            None,
        )
        if pv is None:
            raise KeyError(f"No prompt '{name}' version {version or 'latest'}")
        return pv

    def diff(self, name: str, v1: int, v2: int) -> str:
        """Line-level diff between two versions of a prompt."""
        a = self.get(name, v1).template.splitlines()
        b = self.get(name, v2).template.splitlines()
        import difflib

        lines = list(
            difflib.unified_diff(
                a, b,
                fromfile=f"{name} v{v1}",
                tofile=f"{name} v{v2}",
                lineterm="",
            )
        )
        return "\n".join(lines) or "(no differences)"

    # -- persistence ---------------------------------------------------
    def _save(self):
        if not self.path:
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump([asdict(pv) for pv in self._versions], f, indent=2)

    def _load(self):
        with open(self.path) as f:
            self._versions = [PromptVersion(**row) for row in json.load(f)]

    def export_json(self) -> str:
        return json.dumps([asdict(pv) for pv in self._versions], indent=2)
