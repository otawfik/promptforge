"""Test suite for PromptForge core: store, scorers, models, runner."""

import os
import tempfile

import pytest

from promptforge.datasets import TestCase, TestSet, load_roast_battle
from promptforge.models import LocalResponder, detect_style
from promptforge.runner import Leaderboard, ab_compare, run_eval
from promptforge.scorers import (
    composite_score,
    keyword_score,
    length_score,
    roast_score,
)
from promptforge.store import PromptStore


@pytest.fixture
def store():
    tmp = tempfile.mkdtemp()
    return PromptStore(os.path.join(tmp, "prompts.json"))


@pytest.fixture
def test_set():
    return load_roast_battle()


def test_roast_battle_loads(test_set):
    assert test_set.name == "roast-battle"
    assert len(test_set) == 12
    assert all(isinstance(c, TestCase) for c in test_set.cases)


def test_register_versions(store):
    store.register("roaster", "v1 template {target}", "first")
    pv = store.register("roaster", "v2 template {target}", "second")
    assert pv.version == 2
    assert store.latest("roaster").version == 2
    assert store.get("roaster", 1).template == "v1 template {target}"


def test_render_and_missing_version(store):
    pv = store.register("r", "roast {target}")
    assert pv.render(target="x") == "roast x"
    with pytest.raises(KeyError):
        store.get("r", 99)


def test_diff(store):
    store.register("r", "line one\nline two")
    store.register("r", "line one\nline changed")
    diff = store.diff("r", 1, 2)
    assert "-line two" in diff and "+line changed" in diff


def test_store_persists(tmp_path):
    path = str(tmp_path / "p.json")
    s1 = PromptStore(path)
    s1.register("r", "t {target}")
    s2 = PromptStore(path)
    assert s2.latest("r").version == 1


def test_keyword_score():
    case = TestCase(id="t", input={}, expected_keywords=["pineapple", "pizza"])
    r = keyword_score("pineapple is great", case)
    assert r.score == 0.5


def test_length_score_in_and_out():
    case = TestCase(id="t", input={}, min_words=2, max_words=5)
    assert length_score("a b c", case).score == 1.0
    assert length_score("a", case).score < 1.0


def test_roast_score_orders_spice():
    mild = "What a lovely wonderful target, so nice."
    spicy = "Brutal savage roast, you clown, utterly pathetic and mid."
    assert roast_score(spicy).score > roast_score(mild).score


def test_composite_bounded(test_set):
    case = test_set.cases[0]
    total, breakdown = composite_score("some output words here for testing", case)
    assert 0.0 <= total <= 1.0
    assert len(breakdown) == 6


def test_detect_style():
    assert detect_style("be SAVAGE and ruthless") == "savage"
    assert detect_style("stay polite and wholesome") == "gentle"
    assert detect_style("plain old prompt") == "neutral"


def test_responder_deterministic():
    r = LocalResponder()
    inp = {"target": "pineapple pizza", "context": "party"}
    a = r.respond("be SAVAGE {target}", inp)
    b = r.respond("be SAVAGE {target}", inp)
    assert a == b
    assert "pineapple" in a.lower()


def test_responder_style_differs():
    r = LocalResponder()
    inp = {"target": "gym bros", "context": "locker room"}
    savage = r.respond("be SAVAGE", inp)
    gentle = r.respond("be polite and wholesome", inp)
    assert savage != gentle


def test_run_eval(store, test_set):
    store.register("roaster", "You are SAVAGE. Roast {target} at {context}.")
    result = run_eval(store.latest("roaster"), test_set, LocalResponder())
    assert len(result.cases) == 12
    assert 0.0 <= result.mean_score <= 1.0
    assert all(c.output for c in result.cases)


def test_ab_compare_sorted(store, test_set):
    store.register("r", "be polite {target} {context}")
    store.register("r", "be SAVAGE ruthless {target} {context}")
    v1 = store.get("r", 1)
    v2 = store.get("r", 2)
    ranked = ab_compare([v1, v2], test_set, LocalResponder())
    assert ranked[0].mean_score >= ranked[1].mean_score
    assert ranked[0].prompt_version == 2  # savage should win a roast battle


def test_leaderboard_persists(store, test_set, tmp_path):
    path = str(tmp_path / "board.json")
    store.register("r", "be SAVAGE {target} {context}")
    board = Leaderboard(path)
    board.record(run_eval(store.latest("r"), test_set, LocalResponder()))
    board2 = Leaderboard(path)
    assert len(board2.ranked()) == 1
    assert board2.best()["mean_score"] > 0
