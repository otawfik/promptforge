"""Flask web UI: browse prompts, run evals, A/B compare, view the leaderboard."""

from __future__ import annotations

import os

from flask import Flask, redirect, render_template, request, url_for

from .datasets import load_roast_battle
from .models import LocalResponder
from .runner import Leaderboard, ab_compare, run_eval
from .seeds import seed_store
from .store import PromptStore


def create_app(store: PromptStore | None = None, results_path: str | None = None) -> Flask:
    app = Flask(__name__)

    state_dir = os.path.join(os.path.expanduser("~"), ".promptforge")
    app.config["STORE"] = store or PromptStore(os.path.join(state_dir, "prompts.json"))
    seed_store(app.config["STORE"])
    app.config["BOARD"] = Leaderboard(
        results_path or os.path.join(state_dir, "results.json"))
    app.config["TESTSET"] = load_roast_battle()
    app.config["BACKEND"] = LocalResponder()

    @app.route("/")
    def index():
        store = app.config["STORE"]
        board = app.config["BOARD"]
        best = board.best()
        prompts = [
            {"name": name,
             "versions": sorted(store.versions(name), key=lambda p: p.version, reverse=True)}
            for name in store.names()
        ]
        return render_template("index.html", prompts=prompts, best=best)

    @app.route("/run/<name>")
    def run(name):
        store, board = app.config["STORE"], app.config["BOARD"]
        version = request.args.get("version", type=int)
        prompt = store.get(name, version)
        result = run_eval(prompt, app.config["TESTSET"], app.config["BACKEND"])
        board.record(result)
        return render_template("run.html", result=result)

    @app.route("/compare", methods=["GET", "POST"])
    def compare():
        store, board = app.config["STORE"], app.config["BOARD"]
        results = None
        if request.method == "POST":
            names = request.form.getlist("names")
            prompts = [store.latest(n) for n in names if store.latest(n)]
            if len(prompts) >= 2:
                results = ab_compare(prompts, app.config["TESTSET"], app.config["BACKEND"])
                for r in results:
                    board.record(r)
        return render_template(
            "compare.html", names=store.names(), results=results)

    @app.route("/leaderboard")
    def leaderboard():
        return render_template("leaderboard.html",
                               ranked=app.config["BOARD"].ranked())

    return app
