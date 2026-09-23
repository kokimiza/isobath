"""statistics.md §7.1: cut inference, not a Gaussian plug-in posterior."""

import numpy as np
import pytest

from isobath.inference.project import InferenceConfig, infer, place


def test_cut_no_answers_recovers_full_mixture_and_unseen_mass(model):
    result = infer(model, {}, InferenceConfig(warmup=0, draws=2500, chains=1, seed=23))
    assert np.mean(result.latent, axis=0) == pytest.approx(np.zeros(4), abs=0.06)
    assert result.probabilities[-2] == pytest.approx(0.1, abs=0.015)
    assert sum(result.probabilities.values()) == pytest.approx(1.0)


def test_cut_outer_draws_remain_equal_weight_despite_new_response(model):
    model.arrays["draws_m"][:2, :, 0] = -4.0
    model.arrays["draws_m"][2:, :, 0] = 4.0
    model.arrays["draws_Sigma"] *= 0.001
    result = infer(model, {1: 5}, InferenceConfig(warmup=30, draws=100, chains=2, seed=29))
    assert abs(result.latent[:, 0].mean()) < 0.1
    assert np.unique(result.outer_id, return_counts=True)[1].tolist() == [200] * 4


def test_mapping_failure_and_unseen_remain_distinct(model):
    model.arrays["draws_component_to_region"][:, 0] = -1
    result = infer(model, {}, InferenceConfig(warmup=0, draws=1000, chains=1, seed=3))
    assert result.probabilities[-1] == pytest.approx(0.45, abs=0.03)
    assert result.probabilities[-2] == pytest.approx(0.1, abs=0.02)


def test_partial_ordinal_answers_and_seed_are_reproducible(model):
    cfg = InferenceConfig(warmup=20, draws=40, chains=2, seed=18)
    a, b = infer(model, {1: 5, 4: 1}, cfg), infer(model, {4: 1, 1: 5}, cfg)
    assert np.array_equal(a.latent, b.latent)
    assert np.isfinite(a.coordinates).all()


@pytest.mark.parametrize("value", [0, 6, 2.5, True, float("nan")])
def test_invalid_ordinal_answer_is_rejected(model, value):
    with pytest.raises(ValueError, match="category"):
        infer(model, {1: value})


def test_unknown_question_is_not_imputed(model):
    cfg = InferenceConfig(warmup=0, draws=20, chains=1, seed=42)
    assert np.array_equal(infer(model, {}, cfg).latent, infer(model, {9999: 5}, cfg).latent)


def test_placement_returns_explicit_unmatched_and_credible_distribution(model):
    p = place(model, {}, config=InferenceConfig(warmup=0, draws=300, chains=2, seed=9))
    assert p.unmatched["unseen"] > 0
    assert sum(m["p"] for m in p.memberships) + p.unmatched["total"] == pytest.approx(1.0)
    assert p.draws_x.shape[1] == 2
    assert p.inference_mode == "cut"
