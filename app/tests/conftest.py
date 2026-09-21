import numpy as np
import pytest

from isobath.inference.artifact import Model


def synthetic_model(p=60, k=3, stage="SEED", seed=0) -> Model:
    rng = np.random.default_rng(seed)
    Lambda = rng.normal(0, 0.6, (p, k))
    arrays = {
        "mu": np.full(p, 3.0),
        "scale": np.ones(p),
        "Lambda": Lambda,
        "psi": np.full(p, 0.4),
        "P": np.eye(2, k),
        "c": np.zeros(2),
        "gmm_pi": np.array([0.5, 0.5]),
        "gmm_mean": np.array([[-1.0] + [0.0] * (k - 1), [1.0] + [0.0] * (k - 1)]),
        "gmm_cov": np.stack([np.eye(k) * 0.3] * 2),
    }
    return Model(
        version="test",
        stage=stage,
        item_set_version="0.1",
        question_ids=list(range(1, p + 1)),
        arrays=arrays,
        regions=[{"index": 0, "lineage_id": "REGION-A"}, {"index": 1, "lineage_id": "REGION-B"}],
    )


@pytest.fixture
def model():
    return synthetic_model()
