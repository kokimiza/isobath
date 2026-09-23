import numpy as np
import pytest

from isobath.inference.artifact import Model


def synthetic_model(p=16, k=4, stage="CHARTED", seed=0) -> Model:
    rng = np.random.default_rng(seed)
    s, c = 4, 3
    loadings = rng.normal(0, 0.05, (s, p, k))
    for q in range(p):
        loadings[:, q, q % k] = 0.8
    arrays = {
        "draws_tau": np.tile([-1.0, -0.3, 0.3, 1.0], (s, p, 1)),
        "draws_Lambda": loadings,
        "draws_w": np.tile([0.45, 0.45, 0.1], (s, 1)),
        "draws_m": np.tile(
            np.array([[-1.0] + [0.0] * (k - 1), [1.0] + [0.0] * (k - 1), [0.0] * k]), (s, 1, 1)
        ),
        "draws_Sigma": np.tile(np.eye(k) * 0.5, (s, c, 1, 1)),
        "draws_valid": np.ones((s, c), dtype=bool),
        "draws_occupied": np.tile([True, True, False], (s, 1)),
        "draws_K": np.full(s, c, dtype=int),
        "draws_T": np.full(s, 2, dtype=int),
        "draws_component_to_region": np.tile([0, 1, -2], (s, 1)),
        "draws_core_z": np.empty((s, 0), dtype=int),
        "center_b": np.zeros((s, k)),
        "scale_a": np.ones((s, k)),
        "P": np.eye(k)[[0, min(3, k - 1)]],
        "c": np.zeros(2),
        "T_support": np.array([2]),
        "T_post": np.array([1.0]),
        "K_support": np.array([3]),
        "K_post": np.array([1.0]),
    }
    return Model(
        version="test",
        stage=stage,
        item_set_version="0.1",
        question_ids=list(range(1, p + 1)),
        arrays=arrays,
        regions=[{"index": 0, "lineage_id": "REGION-A"}, {"index": 1, "lineage_id": "REGION-B"}],
        meta={
            "schema_version": 3,
            "inference_mode": "cut",
            "draw_chain": [0, 1, 2, 3],
            "diagnostics": {"p_multiple": 1.0, "p_multiple_mcse": 0.0},
            "seed": seed,
        },
    )


@pytest.fixture
def model():
    return synthetic_model()
