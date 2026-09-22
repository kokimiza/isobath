"""LOCAL DEVELOPMENT ONLY: write a synthetic SEED model for the dummy item bank in seed.sql.

    python -m isobath.devmodel                  # -> app/.dev-models (gitignored)
    MODELS_DIR=.dev-models uvicorn ... / python -m isobath.nightly

Lets the chart, journey and region UI be developed before real data exists. It is random,
not estimated from anything, and must never be used for app/models (the reviewed models).
"""

import sys
from pathlib import Path

import numpy as np

from .inference import artifact

# question ids of supabase/seed.sql: anchors 1..30, blocks 100 + b*20 + j
QUESTION_IDS = list(range(1, 31)) + [100 + b * 20 + j for b in range(10) for j in range(1, 21)]
K = 4


def build(seed: int = 0) -> artifact.Model:
    rng = np.random.default_rng(seed)
    p = len(QUESTION_IDS)
    arrays = {
        "mu": np.full(p, 3.0),
        "scale": np.full(p, 1.1),
        "Lambda": rng.normal(0, 0.5, (p, K)),
        "psi": np.full(p, 0.5),
        "P": np.eye(2, K),
        "c": np.zeros(2),
        "gmm_pi": np.array([0.4, 0.35, 0.25]),
        "gmm_mean": np.array([[-1.0, 0.5, 0, 0], [1.0, 0.5, 0, 0], [0.0, -1.2, 0, 0]]),
        "gmm_cov": np.stack([np.eye(K) * 0.5] * 3),
    }
    return artifact.Model(
        version="dev",
        stage="SEED",
        item_set_version="0.1",
        question_ids=QUESTION_IDS,
        arrays=arrays,
        regions=[
            {"index": 0, "lineage_id": "DEV-A"},
            {"index": 1, "lineage_id": "DEV-B"},
            {"index": 2, "lineage_id": "DEV-C"},
        ],
        meta={"note": "synthetic development model; not estimated from data"},
    )


def main() -> int:
    root = Path(__file__).resolve().parent.parent / ".dev-models"
    artifact.save(build(), root)
    (root / "CURRENT").write_text("dev\n", "utf-8")
    sys.stdout.write(f"{root}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
