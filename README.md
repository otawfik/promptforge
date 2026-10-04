# PromptForge

Test, score, and version prompts like code.

PromptForge is a lightweight prompt engineering workbench. Register prompt templates, version them as you iterate, run them against test sets, score the outputs with local heuristics, A/B test versions head to head, and keep an all-time leaderboard of what worked. No API keys required: a deterministic local mock model and lexicon-based scorers make the whole loop run fully offline, with a documented path to swap in a real LLM when you want one.

The bundled demo is a **roast battle**: three roasting prompt styles (wholesome, savage, structured) compete over 12 roast targets, judged on spice, structure, keyword coverage, and relevance.

## Features

- **Prompt versioning**: every edit to a named prompt becomes a new version, never an overwrite. Diff any two versions.
- **Test sets**: JSON-defined eval cases with expected keywords, word-count bounds, and tags. Ships with a 12-case roast-battle set.
- **Six local scorers**: keyword coverage, length bounds, roast intensity, setup/punchline structure, input relevance, and sentiment polarity, combined into a weighted composite.
- **Deterministic mock LLM**: `LocalResponder` reads the prompt's wording and shifts its style accordingly, so A/B diffs are reproducible without API calls.
- **A/B comparison**: run several prompt versions against the same test set, ranked best first.
- **Persistent leaderboard**: every recorded run is ranked, with the current champion shown in the web UI.
- **Web UI** (Flask) and **CLI** (click) with the same engine underneath.

## Quickstart

```bash
pip install -r requirements.txt

# Run the end-to-end demo (seeds 3 prompt versions, A/B tests them, prints the leaderboard)
python demo.py

# Or use the CLI
python -m promptforge.cli seed
python -m promptforge.cli run roaster --version 2
python -m promptforge.cli compare roaster roaster
python -m promptforge.cli leaderboard
python -m promptforge.cli diff roaster 1 2

# Web UI
python app.py   # then open http://localhost:5001
```

To register your own prompt:

```bash
python -m promptforge.cli register my-prompt \
  --template "Summarize this in one sentence: {text}" \
  --description "v1: terse summarizer" --tag summarization
```

## How the loop works

1. **Register** a prompt template with `{variables}`, e.g. `Roast {target} at {context}`.
2. **Render** it for each test case in a test set (`promptforge/datasets.py`).
3. **Generate** with a model backend (`promptforge/models.py`). The default is `LocalResponder`, a deterministic mock that changes style based on prompt wording ("savage" gets spicy, "wholesome" stays gentle, "setup/punchline" gets structured).
4. **Score** each output with six heuristic scorers (`promptforge/scorers.py`) and a weighted composite.
5. **Compare** versions with `ab_compare` and **rank** everything on the `Leaderboard`.

### The scorers

| Scorer | What it measures |
|---|---|
| `keyword` | Share of expected keywords present in the output |
| `length` | Word count inside the case's min/max bounds |
| `roast` | Roast-lexicon density (spice level) |
| `structure` | Setup/punchline shape: more sentences ending in a punch scores higher |
| `relevance` | Share of the case's input words echoed in the output |
| `sentiment` | Negative polarity lean (roasts should not be neutral mush) |

Default weights: keyword 0.25, relevance 0.20, roast 0.25, structure 0.15, length 0.10, sentiment 0.05. Pass your own `weights` dict to `composite_score` or `run_eval` to retune.

## Using a real LLM

`LLMAdapter` speaks the OpenAI-compatible chat-completions protocol, so it works with OpenAI, Ollama, vLLM, and similar. Configure with environment variables and pass `--llm` to the CLI:

```bash
export PROMPTFORGE_API_BASE=http://localhost:11434/v1  # Ollama, no key needed
export PROMPTFORGE_MODEL=llama3.1
python -m promptforge.cli run roaster --llm
```

## Project structure

```
promptforge/
  store.py       # versioned prompt store (register, get, diff, persist)
  datasets.py    # TestSet / TestCase, JSON loader
  scorers.py     # six local scorers + weighted composite
  models.py      # LocalResponder (mock), LLMAdapter (real LLMs)
  runner.py      # run_eval, ab_compare, Leaderboard
  seeds.py       # starter roast-battle prompts
  cli.py         # click CLI
  web.py         # Flask app factory
  templates/     # Jinja templates
  static/        # CSS
data/
  roast_battle.json   # bundled 12-case test set
app.py           # web entrypoint
demo.py          # end-to-end demo script
tests/           # pytest suite
```

## Running the tests

```bash
pytest tests/ -q
```

## Tech highlights

- Zero-dependency core: the scoring engine, versioning store, and mock model are pure Python (only Flask and click for the interfaces).
- Deterministic generation makes prompt A/B tests reproducible: same prompt plus same input always gives the same output and the same score.
- Prompt history is append-only, so any historical version can be re-run against any test set to check for regressions.

## Screenshots

_Screenshots of the web UI (prompt list, eval run with per-case score breakdowns, A/B comparison, leaderboard) go here. Run `python app.py` and visit http://localhost:5001 to capture them._
