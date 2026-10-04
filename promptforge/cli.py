"""Command-line interface: register, run, compare, rank."""

from __future__ import annotations

import os

import click

from .datasets import load_roast_battle
from .models import LLMAdapter, LocalResponder
from .runner import Leaderboard, ab_compare, run_eval
from .seeds import seed_store
from .store import PromptStore

DEFAULT_DIR = os.path.join(os.path.expanduser("~"), ".promptforge")


def _store(path: str | None) -> PromptStore:
    path = path or os.path.join(DEFAULT_DIR, "prompts.json")
    return PromptStore(path)


def _backend(use_llm: bool):
    return LLMAdapter() if use_llm else LocalResponder()


@click.group()
def cli():
    """PromptForge: test, score, and version prompts like code."""


@cli.command()
@click.option("--store-path", default=None)
def seed(store_path):
    """Register the starter roast-battle prompts."""
    store = _store(store_path)
    seed_store(store)
    click.echo(f"Seeded {len(store.names())} prompt(s) into {store.path or 'memory'}.")


@cli.command()
@click.argument("name")
@click.option("--template", required=True, help="Prompt template with {variables}.")
@click.option("--description", default="")
@click.option("--tag", "tags", multiple=True)
@click.option("--store-path", default=None)
def register(name, template, description, tags, store_path):
    """Register a new prompt (or a new version of an existing one)."""
    store = _store(store_path)
    pv = store.register(name, template, description, list(tags))
    click.echo(f"Registered {pv.name} v{pv.version}.")


@cli.command(name="list")
@click.option("--store-path", default=None)
def list_prompts(store_path):
    """List prompts and their versions."""
    store = _store(store_path)
    for name in store.names():
        click.echo(f"{name}:")
        for pv in store.versions(name):
            click.echo(f"  v{pv.version} - {pv.description or '(no description)'}")


@cli.command()
@click.argument("name")
@click.option("--version", type=int, default=None)
@click.option("--llm", is_flag=True, help="Use the real LLM adapter instead of the local mock.")
@click.option("--store-path", default=None)
@click.option("--results-path", default=None)
def run(name, version, llm, store_path, results_path):
    """Run a prompt version against the roast-battle test set."""
    store = _store(store_path)
    prompt = store.get(name, version)
    test_set = load_roast_battle()
    result = run_eval(prompt, test_set, _backend(llm))
    Leaderboard(results_path or os.path.join(DEFAULT_DIR, "results.json")).record(result)
    click.echo(f"{prompt.name} v{prompt.version} on '{test_set.name}': "
               f"mean score {result.mean_score}")
    for case in result.cases:
        click.echo(f"  [{case.case_id}] {case.total:.3f}  {case.output[:80]}...")


@cli.command()
@click.argument("names", nargs=-1, required=True)
@click.option("--llm", is_flag=True)
@click.option("--store-path", default=None)
@click.option("--results-path", default=None)
def compare(names, llm, store_path, results_path):
    """A/B test prompt versions head-to-head (latest version of each name)."""
    store = _store(store_path)
    prompts = [store.latest(n) for n in names]
    test_set = load_roast_battle()
    board = Leaderboard(results_path or os.path.join(DEFAULT_DIR, "results.json"))
    click.echo(f"A/B on '{test_set.name}' ({len(test_set)} cases):\n")
    for result in ab_compare(prompts, test_set, _backend(llm)):
        board.record(result)
        click.echo(f"  {result.prompt_name} v{result.prompt_version}: {result.mean_score:.4f}")


@cli.command()
@click.option("--results-path", default=None)
def leaderboard(results_path):
    """Show the all-time leaderboard of recorded runs."""
    board = Leaderboard(results_path or os.path.join(DEFAULT_DIR, "results.json"))
    ranked = board.ranked()
    if not ranked:
        click.echo("No runs recorded yet. Run `promptforge run <name>` first.")
        return
    click.echo(f"{'rank':<5}{'prompt':<18}{'set':<16}{'mean':<8}")
    for i, row in enumerate(ranked, 1):
        label = f"{row['prompt_name']} v{row['prompt_version']}"
        click.echo(f"{i:<5}{label:<18}{row['test_set']:<16}{row['mean_score']:<8.4f}")


@cli.command()
@click.argument("name")
@click.argument("v1", type=int)
@click.argument("v2", type=int)
@click.option("--store-path", default=None)
def diff(name, v1, v2, store_path):
    """Show the diff between two versions of a prompt."""
    click.echo(_store(store_path).diff(name, v1, v2))


if __name__ == "__main__":
    cli()
