"""statistics.md §0.1: prespecified continuous comparators share the measurement model."""

import numpy as np
import pytest
from test_statistics_sampler import small_data

from pipeline.export import build_model
from pipeline.research import predictive_density
from pipeline.sampler import SamplerConfig, sample


@pytest.mark.parametrize("structure", ["normal", "student"])
def test_continuous_models_have_one_component_and_integrated_prediction(tmp_path, structure):
    data = small_data(3)
    result = sample(
        data, SamplerConfig(warmup=5, draws=12, chains=2, structure=structure), tmp_path
    )
    assert np.all(result.occupancy == 1)
    model = build_model(data, result, version="baseline", seed=0, commit="test")
    assert np.all(model.arrays["draws_K"] == 1)
    if structure == "student":
        assert np.all(model.arrays["draws_nu"] > 2)
    density = predictive_density(model, {1: 5, 2: 1}, np.random.default_rng(18), samples=100)
    assert np.isfinite(density["log_density"])
