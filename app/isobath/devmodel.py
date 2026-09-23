"""Write a clearly synthetic v3 artifact to .dev-models only; no scientific validation."""

import sys
from pathlib import Path

import numpy as np

from .inference import artifact

QUESTION_IDS = list(range(1, 31)) + [100 + b * 20 + j for b in range(10) for j in range(1, 21)]


def build(seed: int = 0) -> artifact.Model:
    rng = np.random.default_rng(seed)
    s, c, d, j = 4, 3, 16, len(QUESTION_IDS)
    p = np.zeros((2, d))
    p[0, 0], p[1, 3] = 1, 1
    means = np.zeros((s, c, d))
    means[:, 0, 0], means[:, 1, 0] = -1.0, 1.0
    arrays = {
        "draws_tau": np.tile([-1.0, -0.3, 0.3, 1.0], (s, j, 1)),
        "draws_Lambda": rng.normal(0, 0.3, (s, j, d)),
        "draws_w": np.tile([0.45, 0.45, 0.1], (s, 1)),
        "draws_m": means,
        "draws_Sigma": np.tile(np.eye(d) * 0.5, (s, c, 1, 1)),
        "draws_valid": np.ones((s, c), dtype=bool),
        "draws_occupied": np.tile([True, True, False], (s, 1)),
        "draws_K": np.full(s, c),
        "draws_T": np.full(s, 2),
        "draws_component_to_region": np.tile([0, 1, -2], (s, 1)),
        "draws_core_z": np.empty((s, 0), dtype=int),
        "center_b": np.zeros((s, d)),
        "scale_a": np.ones((s, d)),
        "P": p,
        "c": np.zeros(2),
        "T_support": np.array([2]),
        "T_post": np.ones(1),
        "K_support": np.array([3]),
        "K_post": np.ones(1),
    }
    return artifact.Model(
        f"dev-{seed}",
        "CHARTED",
        "0.1",
        {
            "schema_version": 3,
            "inference_mode": "cut",
            "draw_chain": list(range(s)),
            "diagnostics": {"p_multiple": 1.0, "p_multiple_mcse": 0.0, "accepted": False},
            "note": "synthetic development fixture; not estimated or validated",
        },
        QUESTION_IDS,
        arrays,
        [{"index": 0, "lineage_id": "DEV-A"}, {"index": 1, "lineage_id": "DEV-B"}],
    )


def main():
    root = Path(__file__).resolve().parent.parent / ".dev-models"
    model = build()
    artifact.save(model, root)
    (root / "CURRENT").write_text(model.version + "\n", encoding="utf-8")
    sys.stdout.write(f"{root}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
