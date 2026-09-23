"""statistics.md §§2.1, 3, 4: conditional and end-to-end smoke tests."""

import numpy as np
import pytest
from scipy.special import ndtr

from isobath.inference.ordinal import interval_log_probability, truncated_normal
from pipeline.data import Dataset
from pipeline.sampler import SamplerConfig, sample


def test_ordinal_probabilities_normalize_even_in_extreme_tails():
    edges = np.array([-np.inf, -1.0, -0.2, 0.3, 1.0, np.inf])
    for mean in (-40, 0, 40):
        lp = interval_log_probability(edges[:-1] - mean, edges[1:] - mean)
        assert np.isfinite(lp).all()
        assert np.exp(lp).sum() == pytest.approx(1)
    assert np.exp(interval_log_probability(-1.0, 1.0)) == pytest.approx(ndtr(1) - ndtr(-1))


def test_truncation_uses_absolute_bounds_and_handles_far_tails():
    rng = np.random.default_rng(5)
    values = truncated_normal(rng, np.full(100, -40.0), 1.0, 2.0, 3.0)
    assert np.all((values > 2) & (values < 3))


def small_data(n=1):
    return Dataset(
        answers=np.tile([1, 5, 0, 3], (n, 1)),
        question_ids=[1, 2, 3, 4],
        user_ids=[f"person-{i}" for i in range(n)],
        domains=np.array([0, 1, 0, 1]),
        signs=np.array([1, -1, 1, 1]),
        anchors=np.array([True, True, False, False]),
        item_set_version="test",
        dimension=2,
    )


def test_one_person_sampler_preserves_occupancy_and_anchor_signs(tmp_path):
    data = small_data()
    config = SamplerConfig(warmup=5, draws=8, chains=2, seed=81)
    result = sample(data, config, tmp_path)
    assert result.partitions.shape == (2, 8, 1)
    assert np.all(result.occupancy == 1)
    assert result.coordinates.shape == (2, 8, 1, 2)
    assert np.isfinite(result.coordinates).all()
    for draw in result.draws:
        assert draw["Lambda"][0, 0] > 0
        assert draw["Lambda"][1, 1] < 0
        assert np.all(np.diff(draw["tau"], axis=1) > 0)
        assert draw["w"].sum() == pytest.approx(1)
        assert len(draw["w"]) >= 1


def test_invalid_categories_and_missing_anchor_are_rejected():
    data = small_data()
    data.answers[0, 0] = 6
    with pytest.raises(ValueError, match="categor"):
        data.validate()
    data = small_data()
    data.anchors[:] = False
    with pytest.raises(ValueError, match="anchor"):
        data.validate()
