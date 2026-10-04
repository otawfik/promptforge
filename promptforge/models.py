"""Model backends. LocalResponder is a deterministic stand-in that needs no
API key, so prompt iteration and A/B testing work fully offline.

To use a real LLM, swap in LLMAdapter: it speaks the OpenAI-compatible
chat-completions protocol (works with OpenAI, Ollama, vLLM, and friends).
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request


class ModelBackend:
    def respond(self, rendered_prompt: str, test_input: dict) -> str:
        raise NotImplementedError


# -- style detection ----------------------------------------------------
# Markers are checked in a fixed priority order. Note that the generic word
# "roast" is deliberately NOT a savage marker: it appears in every roasting
# prompt, gentle ones included.
_STYLE_MARKERS = {
    "structured": {"setup", "punchline", "three sentences", "three-sentence"},
    "savage": {"savage", "ruthless", "brutal", "destroy", "spicy", "burn",
               "wreck", "clapback"},
    "gentle": {"polite", "kind", "friendly", "wholesome", "gentle", "nice",
               "uplifting"},
}


def detect_style(prompt: str) -> str:
    text = prompt.lower()
    for style, markers in _STYLE_MARKERS.items():
        if any(m in text for m in markers):
            return style
    return "neutral"


# -- deterministic response banks --------------------------------------
_BANKS = {
    "savage": {
        "openers": [
            "Oh, this one's too easy.",
            "Listen, I didn't choose the roast life, the roast life chose your target.",
            "Alright, gloves off.",
        ],
        "bodies": [
            "Calling that {noun} takes real audacity, the delusional kind.",
            "The confidence is honestly impressive, because nothing else about it is.",
            "Somewhere, a {noun} is embarrassed just being associated.",
        ],
        "closers": [
            "Anyway, that was brutal. Stay savage.",
            "Mic drop. No cap needed.",
            "Roasted, toasted, and posted.",
        ],
    },
    "gentle": {
        "openers": [
            "Hey, no judgment here, just love.",
            "Let's keep it light and kind.",
            "Everyone's doing their best, honestly.",
        ],
        "bodies": [
            "Maybe {noun} is just misunderstood, and that's okay.",
            "There's something sweet about a {noun} trying its best.",
            "Honestly, {noun} probably has a good reason.",
        ],
        "closers": [
            "Hugs, not burns.",
            "Stay wholesome out there.",
            "No roasts today, only appreciation.",
        ],
    },
    "neutral": {
        "openers": [
            "Here goes.",
            "Fair warning, this might sting a little.",
        ],
        "bodies": [
            "You have to admit, {noun} is an interesting choice.",
            "There's bold, and then there's {noun}.",
            "Some choices speak for themselves. {noun} shouts.",
        ],
        "closers": [
            "Just my two cents.",
            "Take it or leave it.",
        ],
    },
    "structured": {
        "openers": [],
        "bodies": [],
        "closers": [],
    },
}


def _pick(rng_value: int, options: list[str]) -> str:
    return options[rng_value % len(options)]


def _hash_int(seed: str) -> int:
    return int(hashlib.sha256(seed.encode()).hexdigest(), 16)


class LocalResponder(ModelBackend):
    """Deterministic mock LLM: response style follows the prompt's wording.

    Prompts containing words like 'savage' or 'ruthless' get spicy roasts,
    'polite'/'wholesome' get gentle ones, and prompts asking for a setup and
    punchline get a structured three-sentence roast. Same (prompt, input)
    always yields the same output, which makes A/B diffs reproducible.
    """

    def __init__(self, seed: str = "promptforge"):
        self.seed = seed

    def respond(self, rendered_prompt: str, test_input: dict) -> str:
        style = detect_style(rendered_prompt)
        target = str(test_input.get("target", "your target"))
        context = str(test_input.get("context", ""))
        noun = target.split()[-1].rstrip("s,.")

        if style == "structured":
            return self._structured(target, noun, context)

        bank = _BANKS["savage" if style == "savage" else "gentle" if style == "gentle" else "neutral"]
        h = _hash_int(f"{self.seed}|{style}|{target}|{context}")
        opener = _pick(h, bank["openers"])
        body = _pick(h >> 8, bank["bodies"]).format(noun=noun)
        closer = _pick(h >> 16, bank["closers"])

        topic_echo = f" We're talking about {target} here, in case anyone forgot."
        if context:
            topic_echo += f" At a {context}, no less."
        return f"{opener} {body}{topic_echo} {closer}"

    def _structured(self, target: str, noun: str, context: str) -> str:
        h = _hash_int(f"{self.seed}|structured|{target}|{context}")
        setups = [
            f"Setup: everyone knows someone obsessed with {target}.",
            f"Setup: picture it, {context or 'anywhere'}, and then {target} shows up.",
        ]
        punches = [
            f"Punchline: calling that a personality is generous, even for {noun}.",
            f"Punchline: the audacity is honestly the most impressive part.",
        ]
        tags = ["Anyway, structured roast complete.", "Three sentences, one burn."]
        return " ".join([
            _pick(h, setups),
            _pick(h >> 8, punches),
            _pick(h >> 16, tags),
        ])


class LLMAdapter(ModelBackend):
    """Optional real-LLM backend over any OpenAI-compatible endpoint.

    Configure with environment variables:
      PROMPTFORGE_API_BASE  (e.g. https://api.openai.com/v1, or http://localhost:11434/v1 for Ollama)
      PROMPTFORGE_API_KEY   (not needed for local Ollama)
      PROMPTFORGE_MODEL     (default: gpt-4o-mini)
    """

    def __init__(self, model: str | None = None, base_url: str | None = None,
                 api_key: str | None = None):
        self.model = model or os.environ.get("PROMPTFORGE_MODEL", "gpt-4o-mini")
        self.base_url = (base_url or os.environ.get("PROMPTFORGE_API_BASE",
                                                    "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("PROMPTFORGE_API_KEY", "")

    def respond(self, rendered_prompt: str, test_input: dict) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": rendered_prompt},
                {"role": "user", "content": json.dumps(test_input)},
            ],
            "temperature": 0.7,
            "max_tokens": 256,
        }
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"].strip()
