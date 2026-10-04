"""End-to-end demo: seed prompts, run evals, A/B compare, show leaderboard.

Usage:  python demo.py
"""

import os
import tempfile

from promptforge.datasets import load_roast_battle
from promptforge.models import LocalResponder
from promptforge.runner import Leaderboard, ab_compare
from promptforge.seeds import seed_store
from promptforge.store import PromptStore


def main():
    tmp = tempfile.mkdtemp(prefix="promptforge-demo-")
    store = PromptStore(os.path.join(tmp, "prompts.json"))
    board = Leaderboard(os.path.join(tmp, "results.json"))
    seed_store(store, force=True)

    test_set = load_roast_battle()
    backend = LocalResponder()
    print(f"Test set '{test_set.name}': {len(test_set)} roast-battle cases\n")

    prompts = [store.get("roaster", v) for v in (1, 2, 3)]
    print("Version history for 'roaster':")
    for pv in prompts:
        print(f"  v{pv.version}: {pv.description}")
    print()

    results = ab_compare(prompts, test_set, backend)
    for r in results:
        board.record(r)
        print(f"roaster v{r.prompt_version}: mean {r.mean_score:.4f}")

    print("\nSample output (champion):")
    champ = results[0].cases[0]
    print(f"  [{champ.case_id}] {champ.output}\n")

    print("Leaderboard:")
    for i, row in enumerate(board.ranked(), 1):
        print(f"  {i}. {row['prompt_name']} v{row['prompt_version']}: "
              f"{row['mean_score']:.4f}")

    print(f"\nState saved under {tmp}")


if __name__ == "__main__":
    main()
